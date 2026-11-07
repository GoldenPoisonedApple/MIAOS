
# backup
docker compose -f compose.base.yaml -f compose.deploy.yaml exec -T db \
  sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc --no-owner --no-acl' \
  > ~/backup/miaos_pg_$(TZ=Asia/Tokyo date +%Y%m%d_%H%M%S).dump


# shell
docker compose -f compose.base.yaml -f compose.deploy.yaml exec db /bin/bash

# sql
COPY (
	SELECT
		id,
		name,
		other_metrics->>'attack_score' AS attack_score,
		other_metrics->>'attack_scores_vars' AS attack_scores_vars
	FROM experiments
	WHERE other_metrics ? 'attack_score'
	ORDER BY id
) TO STDOUT WITH CSV HEADER;

# 情報取得
docker compose -f compose.base.yaml -f compose.deploy.yaml exec -T db \
		sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <<'SQL' \
	> ~/backup/miaos_experiments_$(TZ=Asia/Tokyo date +%Y%m%d_%H%M%S).csv
COPY (
  SELECT
    id,
    name,
    other_metrics->>'attack_score' AS attack_score,
    other_metrics->>'attack_scores_vars' AS attack_scores_vars,
		other_metrics->>'target_acc_gaps' AS target_acc_gaps,
		other_metrics->>'attack_model_train_loss' AS attack_model_train_loss,
		other_metrics->>'attack_model_train_acc' AS attack_model_train_acc,
		other_metrics->>'attack_model_train_in_acc' AS attack_model_train_in_acc,
		other_metrics->>'attack_model_train_out_acc' AS attack_model_train_out_acc,
		other_metrics->>'shadow_pair_num_significant_fdr' AS shadow_pair_num_significant_fdr
  FROM experiments
  WHERE other_metrics ? 'attack_score'
	ORDER BY id
) TO STDOUT WITH CSV HEADER;
SQL