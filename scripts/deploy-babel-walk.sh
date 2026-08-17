#!/usr/bin/env bash
set -euo pipefail

host="${1:-bezrabotnyi.com}"
target="/home/roomhacker/apps/babel-walk"
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

rsync -a --delete \
  --include '/experiments/' \
  --include '/experiments/backend_app.py' \
  --include '/experiments/hierarchical_enumerator_v1.py' \
  --include '/experiments/babel_shell_v1.py' \
  --include '/experiments/cluster_counting_mvp.py' \
  --include '/models/' \
  --include '/models/cluster_student_v2/' \
  --include '/models/cluster_student_v2/model.json' \
  --include '/models/top256_alphabet/' \
  --include '/models/top256_alphabet/alphabet_top256.json' \
  --include '/models/top256_markov5/' \
  --include '/models/top256_markov5/***' \
  --include '/models/student_fsm_v1/' \
  --include '/models/student_fsm_v1/student_fsm_v1.json' \
  --include '/models/russian_walk_v1.json' \
  --include '/models/cluster_chunk_counts_v1/' \
  --include '/models/cluster_chunk_counts_v1/len256_block16.json' \
  --include '/site/' \
  --include '/site/***' \
  --exclude '*' \
  "$root/" "$host:$target/"

scp "$root/deploy/babel-walk.service" "$host:/tmp/babel-walk.service"
scp "$root/deploy/all.bezrabotnyi.com.nginx" "$host:/tmp/all.bezrabotnyi.com.nginx"
scp "$root/deploy/babel.bezrabotnyi.com.http.nginx" "$host:/tmp/babel.bezrabotnyi.com.http.nginx"
scp "$root/deploy/babel.bezrabotnyi.com.nginx" "$host:/tmp/babel.bezrabotnyi.com.nginx"
ssh "$host" 'sudo install -m 0644 /tmp/babel-walk.service /etc/systemd/system/babel-walk.service && sudo install -m 0644 /tmp/all.bezrabotnyi.com.nginx /etc/nginx/sites-available/all.bezrabotnyi.com && sudo install -m 0644 /tmp/babel.bezrabotnyi.com.http.nginx /etc/nginx/sites-available/babel.bezrabotnyi.com.http && sudo ln -sfn /etc/nginx/sites-available/all.bezrabotnyi.com /etc/nginx/sites-enabled/all.bezrabotnyi.com && sudo ln -sfn /etc/nginx/sites-available/babel.bezrabotnyi.com.http /etc/nginx/sites-enabled/babel.bezrabotnyi.com.http && sudo rm -f /etc/nginx/sites-enabled/all.bezrabotnyi.com.conf /etc/nginx/sites-enabled/all.bezrabotnost.com && sudo nginx -t && sudo systemctl reload nginx && sudo mkdir -p /var/www/letsencrypt && sudo certbot certonly --webroot -w /var/www/letsencrypt -d babel.bezrabotnyi.com --non-interactive --agree-tos --keep-until-expiring && sudo install -m 0644 /tmp/babel.bezrabotnyi.com.nginx /etc/nginx/sites-available/babel.bezrabotnyi.com && sudo ln -sfn /etc/nginx/sites-available/babel.bezrabotnyi.com /etc/nginx/sites-enabled/babel.bezrabotnyi.com && sudo systemctl daemon-reload && sudo systemctl enable babel-walk && sudo systemctl restart babel-walk && sudo nginx -t && sudo systemctl reload nginx'
