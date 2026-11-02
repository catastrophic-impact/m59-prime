#!/bin/bash
# Make sure the admin account exists (name $M59_ADMIN_ACCOUNT, default "admin"), with the admin character $M59_ADMIN_CHAR (default "dadmin") and ordinary character slots up to 10,
# so the in-game admin console is always at hand and the account can also hold normal characters. Safe to run any time the server answers on the admin port.
# The password comes from $M59_ADMIN_PASSWORD; when it is not set a random one is made and printed ONCE when the account is created (an existing account keeps its password).
ACCT="${M59_ADMIN_ACCOUNT:-admin}"; CHAR="${M59_ADMIN_CHAR:-dadmin}"
A="python3 $(dirname "$0")/admin_prime.py"
out="$($A "show account $ACCT" 2>&1)"
if echo "$out" | grep -q "Cannot find account"; then
  PW="${M59_ADMIN_PASSWORD:-$(head -c 12 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 12)}"
  $A "create account $ACCT $PW $ACCT none" >/dev/null 2>&1
  echo "admin account '$ACCT' created, password: $PW   (write it down: it is not stored anywhere else)"
  out="$($A "show account $ACCT" 2>&1)"
fi
id="$(echo "$out" | grep -E "^ *[0-9]+A? +$ACCT " | head -1 | awk '{print $1}' | tr -d A)"
if [ -n "$id" ]; then
  have="$($A "show account $ACCT" 2>&1 | grep -c -E "^ +$id +[0-9]+ ")"
  # ordinary slots first and the admin character last: the character list shows the newest first, so the Admin slot is the first row
  if ! echo "$out" | grep -q " Admin "; then
    CREATED=1
    while [ "$have" -lt 9 ]; do $A "create user $id" >/dev/null 2>&1; have=$((have + 1)); done
    $A "create admin $id" >/dev/null 2>&1
  else
    while [ "$have" -lt 10 ]; do $A "create user $id" >/dev/null 2>&1; have=$((have + 1)); done
  fi
fi
# name the unnamed admin character (a fresh one shows as <New character> in the client)
line="$($A "show account $ACCT" 2>&1 | grep -E "^ +[0-9]+ +[0-9]+ +Admin +User[0-9]+" | head -1)"
oid="$(echo "$line" | awk '{print $2}')"
[ -n "$oid" ] && $A "send o 0 AdminChangeUserName oUser o $oid sName q $CHAR" >/dev/null 2>&1
# a character that never logged in (piLastLoginTime 0) is listed by the client as "<New character>": mark the admin character as already created
[ -n "$oid" ] && $A "set object $oid piLastLoginTime int 1000000" >/dev/null 2>&1
echo "admin account ready (account $ACCT, 10 character slots, admin character $CHAR)"
[ -n "$CREATED" ] && exit 10      # a new admin character only works after a server restart: the caller restarts the server
exit 0
