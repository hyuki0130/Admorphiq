#!/usr/bin/env bash
# Pull everything admorphiq-related off ceph-build into the repo, so a measurement box
# that is NOT a git repo and has NO backup stops being the only home for work.
#
# WHY THIS EXISTS. On 2026-08-26 the user asked whether ceph-build held history the
# repository did not. It held:
#   - 47 run scripts spanning Jul 19 to Aug 26, none committed, including the whole
#     r56s*/r59s* depth-wave series and the July harness snapshot july_h.tgz
#   - six full-25 DETECT rounds (150 game measurements) from the 2026-08-25 session
#   - four harness diagnostic logs that existed ONLY in /tmp, one reboot from gone —
#     and one of them carried the sharpest finding available (the harness picks `graph`
#     on all nine games tested, while vc33/toggle measurably clears more)
#
# The pattern was: work runs on the box, CONCLUSIONS get written into round pages, and
# the evidence never comes back. Round pages then cite measurements that cannot be
# re-checked from the repository, and a later session inherits the conclusion without
# the data — which is how an off-doctrine axis ran for two days unchallenged.
#
# Run this at the END of any session that touched ceph-build. It is 208K.
set -u
KEY=~/VM/keys/nfw-dev.pem
HOST=ubuntu@ceph-build
cd "$(dirname "$0")/.."

echo "[1/3] loose run scripts and artifacts from the home directory"
ssh -i "$KEY" "$HOST" 'cd ~ && tar czf /tmp/_pull_home.tgz $(ls *_run.sh *_parallel.sh detrun.sh \
   julyrun.sh alt2.sh july_h.tgz framework.tgz *_launcher.log 2>/dev/null | tr "\n" " ") 2>/dev/null' || true
mkdir -p scripts/ceph_home
scp -q -i "$KEY" "$HOST":/tmp/_pull_home.tgz /tmp/ && tar xzf /tmp/_pull_home.tgz -C scripts/ceph_home

echo "[2/3] round directories the repo does not have"
ssh -i "$KEY" "$HOST" 'cd ~/admorphiq && ls scripts/rounds' | LC_ALL=C sort > /tmp/_pull_remote.txt
ls scripts/rounds | LC_ALL=C sort > /tmp/_pull_local.txt
MISSING=$(comm -23 /tmp/_pull_remote.txt /tmp/_pull_local.txt | tr '\n' ' ')
if [ -n "${MISSING// /}" ]; then
  echo "    missing: $MISSING"
  ssh -i "$KEY" "$HOST" "cd ~/admorphiq && tar czf /tmp/_pull_rounds.tgz $(for m in $MISSING; do printf 'scripts/rounds/%s ' "$m"; done) 2>/dev/null"
  scp -q -i "$KEY" "$HOST":/tmp/_pull_rounds.tgz /tmp/ && tar xzf /tmp/_pull_rounds.tgz
else
  echo "    none"
fi

echo "[3/3] diagnostic logs sitting in /tmp — these die on reboot"
mkdir -p scripts/rounds/R99/morning_logs
ssh -i "$KEY" "$HOST" 'ls /tmp/*.log 2>/dev/null' | while read -r f; do
  scp -q -i "$KEY" "$HOST":"$f" scripts/rounds/R99/morning_logs/ 2>/dev/null || true
done
echo "done — now 'git add -A scripts' and commit. Uncommitted work on that box is work that does not exist."
