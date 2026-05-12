# minio_utils.py の実装イメージ
import os
import boto3
import src.core.config as cfg
import mimetypes


def get_s3_client():
	return boto3.client(
		's3',
		endpoint_url=cfg.MINIO_URL,
		aws_access_key_id=cfg.MINIO_ACCESS_KEY,
		aws_secret_access_key=cfg.MINIO_SECRET_KEY,
	)

def download_model_dir(experiment_id: int) -> str:
	"""
	MinIOから指定されたディレクトリ配下のファイルをローカルキャッシュにダウンロードする。
	戻り値として、ローカルの絶対パスを返す。
	"""
	s3 = get_s3_client()
	local_dir_path = os.path.join(cfg.LOCAL_CACHE_DIR, experiment_id)
	os.makedirs(local_dir_path, exist_ok=True)

	# ページネーションを使ってリモートディレクトリ内のオブジェクト一覧を取得
	paginator = s3.get_paginator('list_objects_v2')
	# page: 一度に全てのファイルリストを返すとメモリ不足になるため、ページに分けて取得
	for page in paginator.paginate(Bucket=cfg.MINIO_BUCKET_NAME, Prefix=f"exp/{experiment_id}/"):
		# Contentsがない場合はスキップ
		if "Contents" not in page:
			continue
			
		# Contentsの中身を取得
		# obj: ファイルの情報
		for obj in page["Contents"]:
			remote_file_path = obj["Key"]
			# ローカルキャッシュのパスを作成
			local_file_path = os.path.join(cfg.LOCAL_CACHE_DIR, remote_file_path)
			
			# ディレクトリ自体のキーはスキップ
			if remote_file_path.endswith('/'):
				continue
				
			# ローカルキャッシュのディレクトリを作成
			os.makedirs(os.path.dirname(local_file_path), exist_ok=True)
			
			# --- キャッシュ判定（簡易版） ---
			# ファイルの存在とサイズが一致すれば: 既に存在する場合はダウンロードをスキップする
			# (厳密にやるなら ETag と MD5ハッシュを比較する)
			if os.path.exists(local_file_path) and os.path.getsize(local_file_path) == obj["Size"]:
				print(f"[{cfg.PC_NAME}] Cached: {remote_file_path}")
				continue

			print(f"[{cfg.PC_NAME}] Downloading: {remote_file_path} -> {local_file_path}")
			s3.download_file(cfg.MINIO_BUCKET_NAME, remote_file_path, local_file_path)

	return local_dir_path

def upload_results_dir(local_dir: str, remote_prefix: str):
	"""
	ローカルのディレクトリ(一時ディレクトリ)の中身をすべてMinIOにアップロードする。
	"""
	for root, _, files in os.walk(local_dir):
		for file in files:
			local_file_path = os.path.join(root, file)
			# ローカルパスからの相対パスを計算し、リモートのパスを作成
			relative_path = os.path.relpath(local_file_path, local_dir)
			# ファイル名に prefix を付与
			remote_file_path = os.path.join(remote_prefix, relative_path)
			
			# コンテンツタイプ指定(MINIOで表示可能にするため)
			content_type, _ = mimetypes.guess_type(local_file_path)
			if content_type is None:
				content_type = "application/octet-stream"
			
			
			print(f"[{cfg.PC_NAME}] Uploading: {local_file_path} -> {remote_file_path}")
			s3 = get_s3_client()
			s3.upload_file(local_file_path, cfg.MINIO_BUCKET_NAME, remote_file_path, ExtraArgs={'ContentType': content_type})
