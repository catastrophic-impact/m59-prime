/* PRIME (patch 0083): THE PLAYER'S OWN MOVEMENT, ported from the client (clientd3d/move.c UserMovePlayer / FindIntersection / IntersectNode / SlideAlongWall, which the web client has
 * as packages/world/src/movement.ts). Bots, and the planner that plans for them, move with THIS rule, so a walk a player can make a bot can make: one movement model, not a grid approximation.
 * Units: roo fine (1024 per square), angles 0..4095 with (cos a, sin a) in x/y (x = column, y = row). */
#define CM_FINENESS        1024.0
#define CM_MOVEUNITS       256.0                     /* FINENESS >> 2 */
#define CM_MOVE_DELAY      85.0                      /* ms per MOVEUNITS */
#define CM_STEPS_PER_SEC   210.0
#define CM_STEPS_PER_MOVE  20
#define CM_MAX_STEP_HEIGHT 384.0                     /* 24 * 16 */
#define CM_PLAYER_WIDTH    496.0                     /* 31 * 64 / 4 */
#define CM_PLAYER_HEIGHT   768.0                     /* 3 * FINENESS / 4 */
#define CM_MIN_SIDE_MOVE   64.0                      /* MOVEUNITS / 4 */
#define CM_MIN_DISTANCE    248.0                     /* PLAYER_WIDTH / 2 */
/* the client keeps the plane as exact integers (a,b,c scaled by 1024); the server keeps it as floats, so 'moving exactly parallel to the wall' (equal distance) shows up as a hair more or less: that much counts as equal */
#define CM_PLANE_EPS       0.05
#define CM_SF_DEPTH_MASK   0x3
#define CM_WF_PASSABLE     0x4

static double CMDepth(int d) { static const double D[4] = { 0.0, CM_FINENESS / 5, 2 * CM_FINENESS / 5, 3 * CM_FINENESS / 5 }; return D[d & 3]; }

/* the leaf holding a point, by walking the BSP like the client (on the plane: the right/positive child if it exists, else the left) */
static const BspNode* CMLeafAt(room_type* Room, double x, double y)
{
   if (!Room->TreeNodesCount) return NULL;
   const BspNode* n = &Room->TreeNodes[0];
   while (n && n->Type == BspInternalType)
   {
      double side = (double)n->u.internal.A * x + (double)n->u.internal.B * y + (double)n->u.internal.C;
      const BspNode* next = side == 0 ? (n->u.internal.RightChild ? n->u.internal.RightChild : n->u.internal.LeftChild) : (side > 0 ? n->u.internal.RightChild : n->u.internal.LeftChild);
      if (!next) return NULL;
      n = next;
   }
   return n;
}

static double CMFloorAt(const SectorNode* s, double x, double y)
{
   V2 p; p.X = (float)trunc(x); p.Y = (float)trunc(y);
   return floor((double)SECTORHEIGHTFLOOR(s, &p) + 0.5);
}
static double CMCeilingAt(const SectorNode* s, double x, double y)
{
   V2 p; p.X = (float)trunc(x); p.Y = (float)trunc(y);
   return floor((double)SECTORHEIGHTCEILING(s, &p) + 0.5);
}

/* floor minus the water depth at a point (client GetFloorBase); false when the point is on no floor */
static bool CMFloorBase(room_type* Room, double x, double y, double* out)
{
   const BspNode* leaf = CMLeafAt(Room, x, y);
   if (!leaf || leaf->Type != BspLeafType || !leaf->u.leaf.Sector) return false;
   const SectorNode* s = leaf->u.leaf.Sector;
   *out = CMFloorAt(s, x, y) - CMDepth((int)(s->Flags & CM_SF_DEPTH_MASK));
   return true;
}

/* bspload.c SetWallHeights: z1 = the top of the lower wall, z2 = the bottom of the upper wall, both at the wall's first end point */
static void CMWallHeights(const Wall* w, double* z1, double* z2)
{
   const SectorNode* S1 = w->RightSector; const SectorNode* S2 = w->LeftSector;   /* pos = right, neg = left */
   if (!S1 && !S2) { *z1 = 0; *z2 = CM_FINENESS; return; }
   if (!S1 || !S2) { const SectorNode* S = S1 ? S1 : S2; *z1 = CMFloorAt(S, w->P1.X, w->P1.Y); *z2 = CMCeilingAt(S, w->P1.X, w->P1.Y); return; }
   double a0 = CMFloorAt(S1, w->P1.X, w->P1.Y), b0 = CMFloorAt(S2, w->P1.X, w->P1.Y), a1 = CMFloorAt(S1, w->P2.X, w->P2.Y), b1 = CMFloorAt(S2, w->P2.X, w->P2.Y);
   if (a0 > b0) *z1 = a0; else *z1 = (b1 >= a1) ? b0 : a0;
   double c0 = CMCeilingAt(S1, w->P1.X, w->P1.Y), d0 = CMCeilingAt(S2, w->P1.X, w->P1.Y);
   *z2 = (c0 > d0) ? d0 : c0;
}

/* move.c IntersectNode: the first wall of this splitter that blocks the step */
static Wall* CMIntersectNode(const BspNode* n, double oldX, double oldY, double newX, double newY, double z)
{
   const double md = CM_MIN_DISTANCE;
   if (n->BoundingBox.Min.X - newX > md || newX - n->BoundingBox.Max.X > md || n->BoundingBox.Min.Y - newY > md || newY - n->BoundingBox.Max.Y > md) return NULL;
   const double planeDistance = (double)n->u.internal.A * newX + (double)n->u.internal.B * newY + (double)n->u.internal.C;
   const double oldDistance = (double)n->u.internal.A * oldX + (double)n->u.internal.B * oldY + (double)n->u.internal.C;
   if (fabs(planeDistance) > md || fabs(planeDistance) > fabs(oldDistance) + CM_PLANE_EPS) return NULL;
   const double md2 = md * md;
   for (Wall* w = n->u.internal.FirstWall; w; w = w->NextWallInPlane)
   {
      const double x0 = w->P1.X, y0 = w->P1.Y, x1 = w->P2.X, y1 = w->P2.Y;
      if (newX < fmin(x0, x1) - md || newX > fmax(x0, x1) + md) continue;
      if (newY < fmin(y0, y1) - md || newY > fmax(y0, y1) + md) continue;
      const Side* sd = oldDistance > 0 ? w->RightSide : w->LeftSide;
      const SectorNode* other = oldDistance > 0 ? w->LeftSector : w->RightSector;
      if (!sd) continue;
      const double belowHeight = other ? CMDepth((int)(other->Flags & CM_SF_DEPTH_MASK)) : 0.0;
      double z1, z2; CMWallHeights(w, &z1, &z2);
      if ((!sd->TextureLower || z1 - belowHeight - z <= CM_MAX_STEP_HEIGHT) && (!sd->TextureUpper || z2 - z >= CM_PLAYER_HEIGHT) && (sd->Flags & CM_WF_PASSABLE))
         continue;
      double ddx = newX - x0, ddy = newY - y0; const double d0 = ddx * ddx + ddy * ddy;
      ddx = newX - x1; ddy = newY - y1; const double d1 = ddx * ddx + ddy * ddy;
      const double lx = x1 - x0, ly = y1 - y0, lenWall2 = lx * lx + ly * ly;
      if (d0 > lenWall2) { const double ox = oldX - x1, oy = oldY - y1; if (d1 < md2 && d1 <= ox * ox + oy * oy) return w; }
      else if (d1 > lenWall2) { const double ox = oldX - x0, oy = oldY - y0; if (d0 < md2 && d0 <= ox * ox + oy * oy) return w; }
      else return w;
   }
   return NULL;
}

/* move.c FindIntersection: depth first over the internal nodes */
static Wall* CMFindIntersection(const BspNode* n, double oldX, double oldY, double newX, double newY, double z)
{
   if (!n || n->Type != BspInternalType) return NULL;
   Wall* w = CMIntersectNode(n, oldX, oldY, newX, newY, z);
   if (w) return w;
   w = CMFindIntersection(n->u.internal.RightChild, oldX, oldY, newX, newY, z);
   if (w) return w;
   return CMFindIntersection(n->u.internal.LeftChild, oldX, oldY, newX, newY, z);
}

/* move.c SlideAlongWall: keep the component of the move along the wall */
static void CMSlide(const Wall* w, double xOld, double yOld, double* xNew, double* yNew)
{
   const double dx = *xNew - xOld, dy = *yNew - yOld, wx = (double)w->P2.X - w->P1.X, wy = (double)w->P2.Y - w->P1.Y;
   const double num = dx * wx + dy * wy; double denom = wx * wx + wy * wy; if (denom == 0) denom = 1;
   *xNew = xOld + floor(wx * num / denom + 0.5);
   *yNew = yOld + floor(wy * num / denom + 0.5);
}

/* ONE tick of the player's walk (UserMovePlayer): from (*x,*y) heading `angle` for `dt` ms (85 = the client's MOVE_DELAY, one MOVEUNITS), `run` doubles the distance.
 * Returns true when the position changed; *offRoom is set when the step ran off the room's edge (the client then asks the server for an edge exit). Walls only: creatures are the caller's. */
int g_cmDebug = 0;
bool BSPClientMove(room_type* Room, double* x, double* y, int angle, double dt, bool run, bool* offRoom)
{
   if (offRoom) *offRoom = false;
   if (!Room || !Room->TreeNodesCount) return false;
   double distance = run ? 2 * CM_MOVEUNITS : CM_MOVEUNITS;
   const BspNode* leaf0 = CMLeafAt(Room, *x, *y);
   int depth = (leaf0 && leaf0->Type == BspLeafType && leaf0->u.leaf.Sector) ? (int)(leaf0->u.leaf.Sector->Flags & CM_SF_DEPTH_MASK) : 0;
   { static const double F[4] = { 1.0, 0.75, 0.5, 0.25 }; distance = distance * F[depth]; }
   if (dt < 1) dt = 1;
   if (dt < CM_MOVE_DELAY) distance = distance * dt / CM_MOVE_DELAY;
   const double rad = (double)(angle & 4095) * 2.0 * M_PI / 4096.0;
   const double dx = trunc(distance * cos(rad)), dy = trunc(distance * sin(rad));
   int numSteps = (int)floor(CM_STEPS_PER_SEC * dt / 1000.0); if (numSteps > CM_STEPS_PER_MOVE) numSteps = CM_STEPS_PER_MOVE; if (numSteps < 1) numSteps = 1;
   const double xinc = trunc(dx / numSteps), yinc = trunc(dy / numSteps);
   double lastX = *x, lastY = *y, nx = lastX, ny = lastY; bool moved = false;
   double zStand; if (!CMFloorBase(Room, lastX, lastY, &zStand)) zStand = 0;   /* a walking body stands on the floor: the client's z (which lags only while climbing) is the floor here */
   for (int i = 0; i < numSteps; i++)
   {
      nx = lastX + xinc; ny = lastY + yinc;
      double fb; double z = CMFloorBase(Room, lastX, lastY, &fb) ? (zStand > fb ? zStand : fb) : zStand;
      const BspNode* leaf = CMLeafAt(Room, nx, ny);
      if (!leaf || leaf->Type != BspLeafType || !leaf->u.leaf.Sector) { nx = lastX; ny = lastY; break; }
      Wall* wall = CMFindIntersection(&Room->TreeNodes[0], lastX, lastY, nx, ny, z);
      if (g_cmDebug) printf("  sub %d from %.0f %.0f to %.0f %.0f z %.0f first wall %p (%.0f,%.0f)-(%.0f,%.0f)\n", i, lastX, lastY, nx, ny, z, (void*)wall, wall?wall->P1.X:0, wall?wall->P1.Y:0, wall?wall->P2.X:0, wall?wall->P2.Y:0);
      if (wall) CMSlide(wall, lastX, lastY, &nx, &ny);
      wall = CMFindIntersection(&Room->TreeNodes[0], lastX, lastY, nx, ny, z);
      if (wall)
      {
         CMSlide(wall, lastX, lastY, &nx, &ny);
         wall = CMFindIntersection(&Room->TreeNodes[0], lastX, lastY, nx, ny, z);
         if (wall)
         {
            static const int sides[2] = { 3, 1 };
            for (int k = 0; k < 2; k++)
            {
               const double a = (double)((angle + sides[k] * 4096 / 4) % 4096) * (2.0 * M_PI / 4096.0);
               nx = lastX + trunc(CM_MIN_SIDE_MOVE * cos(a)); ny = lastY + trunc(CM_MIN_SIDE_MOVE * sin(a));
               wall = CMFindIntersection(&Room->TreeNodes[0], lastX, lastY, nx, ny, z);
               if (!wall) break;
            }
            if (wall) { nx = lastX; ny = lastY; break; }
         }
      }
      if (nx <= 0 || nx >= Room->ThingsBox.Max.X || ny <= 0 || ny >= Room->ThingsBox.Max.Y) { if (offRoom) *offRoom = true; nx = lastX; ny = lastY; break; }
      lastX = nx; lastY = ny; moved = true;
   }
   if (!moved && nx == *x && ny == *y) return false;
   *x = nx; *y = ny;
   return true;
}
