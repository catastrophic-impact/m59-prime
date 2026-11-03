// PLANLAB: the server's own planner (roofile.c compiled in, nothing changed) run on a .roo file without a server.
//   planlab ROO.roo [-v] [-a r,c ...avoid squares] < lines of "srow scol grow gcol" (game squares, 1-based like the server's Kod; middle of the square)
// prints per line: WAY/NO, the waypoint, milliseconds.
#include "roofile.c"
#include "clientmove.inc"
#include <stdarg.h>
void* AllocateMemoryDebug(int id,int sz,const char*f,int l){ return calloc(1,sz); }
void* AllocateMemorySIMD(int id,int sz){ return calloc(1,sz); }
void FreeMemorySIMD(int id,void*p,int sz){ free(p); }
void FreeMemoryX(int id,void**p,int sz){ free(*p); *p=NULL; }
void eprintf(const char*fmt,...){ va_list a; va_start(a,fmt); vfprintf(stderr,fmt,a); va_end(a); }
int main(int argc,char**argv){
   if(argc<2){ fprintf(stderr,"usage\n"); return 1; }
   static room_type room; memset(&room,0,sizeof room);
   if(!BSPLoadRoom(argv[1],&room)){ fprintf(stderr,"cannot load %s\n",argv[1]); return 1; }
   room.roomdata_id=1;
   { for(int i=0;i<3;i++){ BspNode*n=&room.TreeNodes[i]; if(n->Type==BspInternalType) printf("srv node %d A %f B %f C %f bbox %f %f %f %f firstwall %d right %d left %d\n",i,n->u.internal.A,n->u.internal.B,n->u.internal.C,n->BoundingBox.Min.X,n->BoundingBox.Min.Y,n->BoundingBox.Max.X,n->BoundingBox.Max.Y,n->u.internal.FirstWallNum,n->u.internal.RightChildNum,n->u.internal.LeftChildNum); } Wall*w=&room.Walls[0]; printf("srv wall0 %f %f %f %f rightside %d leftside %d rsec %d lsec %d\n",w->P1.X,w->P1.Y,w->P2.X,w->P2.Y,w->RightSide?1:0,w->LeftSide?1:0,w->RightSectorNum,w->LeftSectorNum); }
   if(argc>3 && !strcmp(argv[2],"-d")){ // DIFFERENTIAL TEST against the client's mover: lines "x y angle dt run nx ny"
      FILE*f=fopen(argv[3],"r"); double x,y,nx,ny; int ang,dt,run; long n=0,bad=0; while(fscanf(f,"%lf %lf %d %d %d %lf %lf",&x,&y,&ang,&dt,&run,&nx,&ny)==7){ double px=x,py=y; bool off; BSPClientMove(&room,&px,&py,ang,dt,run!=0,&off); n++; if(fabs(px-nx)>0.5||fabs(py-ny)>0.5){ if(bad<400){ const BspNode*lf=CMLeafAt(&room,x,y); const SectorNode*sc=lf&&lf->Type==BspLeafType?lf->u.leaf.Sector:NULL; static long cd=0,cs=0,cn=0; if(sc){ if(sc->Flags&3) cd++; if(sc->SlopeInfoFloor||sc->SlopeInfoCeiling) cs++; cn++; } if(bad==399) printf("  of the first 400 mismatches: start sector has water depth %ld, slope %ld, of %ld\n",cd,cs,cn); } if(bad<3) printf("  MISMATCH start (%.0f,%.0f) angle %d dt %d run %d: client (%.0f,%.0f) port (%.0f,%.0f)\n",x,y,ang,dt,run,nx,ny,px,py); bad++; } }
      printf("%s: %ld steps, %ld differ\n",argv[1],n,bad); return 0; }
   if(argc>6 && !strcmp(argv[2],"-t")){ g_cmDebug=1; double x=atof(argv[3]),y=atof(argv[4]); int a=atoi(argv[5]); bool off; BSPClientMove(&room,&x,&y,a,atof(argv[6]),false,&off); printf("port result %.0f %.0f\n",x,y); return 0; }
   bool verbose=false;
   for(int i=2;i<argc;i++){
      if(!strcmp(argv[i],"-v")) verbose=true;
      else if(!strcmp(argv[i],"-a") && i+1<argc){ int r,c; sscanf(argv[++i],"%d,%d",&r,&c); if(g_AvoidN<MAXAVOIDSQUARES){ g_AvoidRow[g_AvoidN]=r; g_AvoidCol[g_AvoidN]=c; g_AvoidN++; } }
   }
   if(verbose){ // DEBUG: the cells within one square of the exit (84,49): floor? reachable from (6,5)? straight walk to the goal?
      FPGrid* g=FPGetGrid(&room); V2 E; E.X=48*1024.0f+512; E.Y=83*1024.0f+512;
      std::vector<char> seen(g->ncols*g->nrows,0); std::vector<int> q; int st=(int)(5.5f*1024/FPG_CELL)*g->ncols+(int)(4.5f*1024/FPG_CELL); q.push_back(st); seen[st]=1;
      for(size_t h=0;h<q.size();h++){ int u=q[h],r=u/g->ncols,c=u%g->ncols; for(int d=0;d<8;d++) if(g->links[u]&(1<<d)){ int v=(r+FPG_DR[d])*g->ncols+c+FPG_DC[d]; if(!seen[v]){seen[v]=1;q.push_back(v);} } }
      printf("flood from (6,5): %zu cells\n",q.size());
      { int nearAll=0,nearReach=0; for(int r=0;r<g->nrows;r++)for(int c=0;c<g->ncols;c++){ V2 cc; cc.X=(c+.5f)*FPG_CELL; cc.Y=(r+.5f)*FPG_CELL; float dx=cc.X-E.X,dy=cc.Y-E.Y; if(dx*dx+dy*dy<=1024.0f*1024.0f && g->links[r*g->ncols+c]){ nearAll++; if(seen[r*g->ncols+c]) nearReach++; } } printf("floor cells within 1 square of the exit: %d, of them reachable from (6,5): %d\n",nearAll,nearReach); }
      for(int r=0;r<g->nrows;r++)for(int c=0;c<g->ncols;c++){ V2 cc; cc.X=(c+.5f)*FPG_CELL; cc.Y=(r+.5f)*FPG_CELL; float dx=cc.X-E.X,dy=cc.Y-E.Y; if(dx*dx+dy*dy<=1024.0f*1024.0f && seen[r*g->ncols+c]){ bool w=FPWalk(&room,&cc,&E,0); printf("REACHABLE near cell (%.0f,%.0f) dist %.0f straight %d wall (%.0f,%.0f)-(%.0f,%.0f) sectors %d %d\n",cc.X,cc.Y,sqrtf(dx*dx+dy*dy),(int)w,fp_lastWall?fp_lastWall->P1.X:0,fp_lastWall?fp_lastWall->P1.Y:0,fp_lastWall?fp_lastWall->P2.X:0,fp_lastWall?fp_lastWall->P2.Y:0,fp_lastWall?fp_lastWall->RightSectorNum:-1,fp_lastWall?fp_lastWall->LeftSectorNum:-1); } }
      { printf("MAP rows 82..88 (1/8 steps), cols 47..55 (game squares): . reachable floor, o floor not reachable from (6,5), # no floor\n"); for(int r=82*8-8;r<88*8;r+=1){ printf("%6.2f ",(r+.5)/8.0+0.5-0.5+0); for(int c=46*8;c<55*8;c+=1){ int u=r*g->ncols+c; putchar(g->links[u]? (seen[u]?'.':'o') : '#'); } putchar('\n'); } }
      { printf("BRIDGES: reachable floor cell A and unreachable floor cell B within 4 cells where the straight walk A->B is allowed\n"); int n=0; for(int r=0;r<g->nrows&&n<10;r++)for(int c=0;c<g->ncols&&n<10;c++){ int u=r*g->ncols+c; if(!seen[u]) continue; for(int dr=-4;dr<=4&&n<10;dr++)for(int dc=-4;dc<=4&&n<10;dc++){ int rr=r+dr,cc2=c+dc; if(rr<0||cc2<0||rr>=g->nrows||cc2>=g->ncols) continue; int v=rr*g->ncols+cc2; if(!g->links[v]||seen[v]) continue; V2 a,b; a.X=(c+.5f)*FPG_CELL;a.Y=(r+.5f)*FPG_CELL;b.X=(cc2+.5f)*FPG_CELL;b.Y=(rr+.5f)*FPG_CELL; if(FPWalk(&room,&a,&b,0)){ printf("  A game(%.2f,%.2f) -> B game(%.2f,%.2f) straight walk allowed, no grid link\n",a.Y/1024+1,a.X/1024+1,b.Y/1024+1,b.X/1024+1); n++; } } } printf("bridges shown %d\n",n); }
      { V2 a; a.X=50624;a.Y=85824; FPWalk(&room,&a,&E,0); Wall* w=fp_lastWall; if(w){ printf("WALL (%.0f,%.0f)-(%.0f,%.0f) right side: id %d flags 0x%x tex %d/%d/%d sectorR %d | left side: id %d flags 0x%x\n",w->P1.X,w->P1.Y,w->P2.X,w->P2.Y,w->RightSide?w->RightSide->ServerID:-1,w->RightSide?w->RightSide->Flags:0,w->RightSide?w->RightSide->TextureMiddle:0,w->RightSide?w->RightSide->TextureUpper:0,w->RightSide?w->RightSide->TextureLower:0,w->RightSectorNum,w->LeftSide?w->LeftSide->ServerID:-1,w->LeftSide?w->LeftSide->Flags:0); if(w->RightSector) printf(" right sector floor %.0f ceil %.0f\n",w->RightSector->FloorHeight,w->RightSector->CeilingHeight); if(w->LeftSector) printf(" left sector floor %.0f ceil %.0f\n",w->LeftSector->FloorHeight,w->LeftSector->CeilingHeight);} }
      { printf("WALLS with a server id (doors, gates, movable walls) in Marion:\n"); int n=0; for(int i=0;i<room.WallsCount;i++){ Wall*w=&room.Walls[i]; int ri=w->RightSide?w->RightSide->ServerID:0, li=w->LeftSide?w->LeftSide->ServerID:0; if(ri||li){ printf("  id %d/%d flags %x/%x  game (%.1f,%.1f)-(%.1f,%.1f)\n",ri,li,w->RightSide?w->RightSide->Flags:0,w->LeftSide?w->LeftSide->Flags:0,w->P1.Y/1024+1,w->P1.X/1024+1,w->P2.Y/1024+1,w->P2.X/1024+1); n++; } } printf("  total %d of %d walls\n",n,(int)room.WallsCount); }
      { int pts[][2]={{6,5},{15,2},{30,66},{32,17},{32,43},{50,22},{55,28},{56,53},{62,57},{80,15},{84,49},{31,67},{44,1},{84,51},{86,49},{87,49}}; for(auto&p:pts){ int r=(int)((p[0]-1)*1024+512)/128, c=(int)((p[1]-1)*1024+512)/128; int u=r*g->ncols+c; printf("point game(%d,%d): %s\n",p[0],p[1],g->links[u]?(seen[u]?"floor, main region":"floor, NOT main region"):"no floor"); } }
      { printf("BRIDGES to the exit island (B within 2 squares of the exit, not main region):\n"); int n=0; V2 Ex; Ex.X=48*1024.0f+512; Ex.Y=83*1024.0f+512; for(int r=0;r<g->nrows&&n<12;r++)for(int c=0;c<g->ncols&&n<12;c++){ int u=r*g->ncols+c; if(!seen[u]) continue; V2 a;a.X=(c+.5f)*FPG_CELL;a.Y=(r+.5f)*FPG_CELL; if((a.X-Ex.X)*(a.X-Ex.X)+(a.Y-Ex.Y)*(a.Y-Ex.Y)>3072.0f*3072.0f) continue; for(int dr=-12;dr<=12&&n<12;dr++)for(int dc=-12;dc<=12&&n<12;dc++){ int rr=r+dr,cc2=c+dc; if(rr<0||cc2<0||rr>=g->nrows||cc2>=g->ncols) continue; int v=rr*g->ncols+cc2; if(!g->links[v]||seen[v]) continue; V2 b;b.X=(cc2+.5f)*FPG_CELL;b.Y=(rr+.5f)*FPG_CELL; if((b.X-Ex.X)*(b.X-Ex.X)+(b.Y-Ex.Y)*(b.Y-Ex.Y)>2048.0f*2048.0f) continue; if(FPWalk(&room,&a,&b,0)){ printf("  main game(%.2f,%.2f) -> island game(%.2f,%.2f): real walk check ALLOWS, grid has no link\n",a.Y/1024+1,a.X/1024+1,b.Y/1024+1,b.X/1024+1); n++; } } } printf("bridges %d\n",n); }
      { printf("COLUMN game col 51, rows 83..88 (roo x=%d): region per 1/4 square\n",50*1024+512); for(float rr=83.0f;rr<=88.0f;rr+=0.25f){ int r=(int)(((rr-1)*1024+512)/128), c=(int)((50*1024+512)/128); int u=r*g->ncols+c; printf("  row %.2f: %s\n",rr,g->links[u]?(seen[u]?"MAIN":"island"):"no floor"); } }
      { for(float rr=84.375f;rr<=84.875f;rr+=0.0625f){ V2 a,b; a.X=50*1024.0f+512; a.Y=(84.0f-1)*1024+rr*0+ (84.375f-0.5f)*1024; b=a; b.Y=(rr-0.5f)*1024+64; Wall*bw=NULL; V2 a2=a; a2.Y=(rr-0.5f)*1024; V2 b2=a2; b2.Y+=128; bool ok=BSPCanMoveInRoom(&room,&a2,&b2,0,false,&bw); printf("  step south from row %.3f to %.3f at col 51: %s %s",rr,rr+0.125f,ok?"allowed":"REFUSED",bw?"wall":""); if(bw){ printf(" (%.0f,%.0f)-(%.0f,%.0f) right id %d left id %d",bw->P1.X,bw->P1.Y,bw->P2.X,bw->P2.Y,bw->RightSide?bw->RightSide->ServerID:-1,bw->LeftSide?bw->LeftSide->ServerID:-1); } printf("\n"); } }
      int shown=0; for(int r=0;r<g->nrows;r++)for(int c=0;c<g->ncols;c++){ V2 cc; cc.X=(c+.5f)*FPG_CELL; cc.Y=(r+.5f)*FPG_CELL; float dx=cc.X-E.X,dy=cc.Y-E.Y; if(dx*dx+dy*dy<=1024.0f*1024.0f && g->links[r*g->ncols+c]){ bool w=FPWalk(&room,&cc,&E,0); if(shown<12){ printf("floor cell (%.0f,%.0f) dist %.0f links %d straight-walk %d wall %p\n",cc.X,cc.Y,sqrtf(dx*dx+dy*dy),__builtin_popcount(g->links[r*g->ncols+c]),(int)w,(void*)fp_lastWall); shown++; } } }
      printf("shown %d\n",shown); }
   if(argc>2 && !strcmp(argv[2],"-p")){ // PATH CHECK: the client walker's positions (P x y, roo units) judged step by step by the server's own check
      FILE*f=fopen(argv[3],"r"); char ln[128]; double px=0,py=0; bool first=true; int step=0,bad=0;
      while(fgets(ln,sizeof ln,f)){ double x,y; if(sscanf(ln,"P %lf %lf",&x,&y)!=2) continue; if(!first){ V2 a,b; a.X=px;a.Y=py;b.X=x;b.Y=y; Wall*bw=NULL; bool ok=BSPCanMoveInRoom(&room,&a,&b,0,false,&bw); if(!ok){ bad++; printf("step %d REFUSED by the server check: from game(%.2f,%.2f) to game(%.2f,%.2f) len %.0f  %s",step,py/1024+0.5,px/1024+0.5,y/1024+0.5,x/1024+0.5,hypot(x-px,y-py),bw?"wall":"no wall (left the floor)"); if(bw) printf(" (%.0f,%.0f)-(%.0f,%.0f)",bw->P1.X,bw->P1.Y,bw->P2.X,bw->P2.Y); printf("\n"); } } first=false; px=x;py=y;step++; }
      printf("%d steps, %d refused\n",step,bad);
      { FPGrid* g=FPGetGrid(&room); std::vector<char> seen(g->ncols*g->nrows,0); std::vector<int> q; int st=(int)(5.5f*1024/FPG_CELL)*g->ncols+(int)(4.5f*1024/FPG_CELL); q.push_back(st); seen[st]=1;
        for(size_t h=0;h<q.size();h++){ int u=q[h],r=u/g->ncols,c=u%g->ncols; for(int d=0;d<8;d++) if(g->links[u]&(1<<d)){ int v=(r+FPG_DR[d])*g->ncols+c+FPG_DC[d]; if(!seen[v]){seen[v]=1;q.push_back(v);} } }
        rewind(f); while(fgets(ln,sizeof ln,f)){ double x,y; if(sscanf(ln,"P %lf %lf",&x,&y)!=2) continue; int c=(int)(x/FPG_CELL),r=(int)(y/FPG_CELL),u=r*g->ncols+c; printf("  game(%.2f,%.2f) cell %s links %d\n",y/1024+0.5,x/1024+0.5,g->links[u]?(seen[u]?"MAIN":"island"):"no floor",__builtin_popcount(g->links[u])); } }
      return 0; }
   int sr,sc,gr,gc; char line[256];
   while(fgets(line,sizeof line,stdin)){
      if(sscanf(line,"%d %d %d %d",&sr,&sc,&gr,&gc)!=4) continue;
      V2 S,E,P; S.X=(sc-1)*1024.0f+512; S.Y=(sr-1)*1024.0f+512; E.X=(gc-1)*1024.0f+512; E.Y=(gr-1)*1024.0f+512;
      // the goal square is not avoided (as PathAvoidDoors does)
      int saveN=g_AvoidN; int k=0; int rr[MAXAVOIDSQUARES],cc2[MAXAVOIDSQUARES];
      for(int i=0;i<saveN;i++) if(!(g_AvoidRow[i]==gr&&g_AvoidCol[i]==gc)){ rr[k]=g_AvoidRow[i]; cc2[k]=g_AvoidCol[i]; k++; }
      int sR[MAXAVOIDSQUARES],sC[MAXAVOIDSQUARES]; memcpy(sR,g_AvoidRow,sizeof sR); memcpy(sC,g_AvoidCol,sizeof sC);
      memcpy(g_AvoidRow,rr,sizeof rr); memcpy(g_AvoidCol,cc2,sizeof cc2); g_AvoidN=k;
      clock_t t0=clock(); bool ok=BSPFindPathStep(&room,&S,&E,&P,0); double ms=(clock()-t0)*1000.0/CLOCKS_PER_SEC;
      memcpy(g_AvoidRow,sR,sizeof sR); memcpy(g_AvoidCol,sC,sizeof sC); g_AvoidN=saveN;
      printf("(%d,%d)->(%d,%d) %s  waypoint (%.2f,%.2f) squares  %.0f ms\n",sr,sc,gr,gc,ok?"WAY":"NO WAY",P.Y/1024.0+0.5,P.X/1024.0+0.5,ms);
   }
   return 0;
}
