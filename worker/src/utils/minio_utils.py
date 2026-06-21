# minio_utils.py の実装イメージ
import os
import boto3
import src.core.config as cfg
import mimetypes

# logファイルをtext/plainとして認識させる
mimetypes.add_type("text/plain", ".log")

FILTERS_PREFIX = "filters/"
RESULTS_PREFIX = "results/"


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=cfg._MINIO_URL,
        aws_access_key_id=cfg._MINIO_ACCESS_KEY,
        aws_secret_access_key=cfg._MINIO_SECRET_KEY,
    )


def _results_remote_prefix(experiment_id: int) -> str:
    return f"{RESULTS_PREFIX}{experiment_id}/"


def download_filter(filter_id: str) -> str:
    """
    MinIO の filters/{filter_id}.png をローカルキャッシュにダウンロードする。
    戻り値としてローカルの絶対パスを返す。
    """
    remote_key = f"{FILTERS_PREFIX}{filter_id}.png"
    local_dir = os.path.join(cfg.LOCAL_CACHE_DIR, "filters")
    os.makedirs(local_dir, exist_ok=True)
    local_path = os.path.join(local_dir, f"{filter_id}.png")

    s3 = get_s3_client()
    if os.path.isfile(local_path):
        try:
            head = s3.head_object(Bucket=cfg._MINIO_BUCKET_NAME, Key=remote_key)
            if os.path.getsize(local_path) == head["ContentLength"]:
                print(f"[{cfg.PC_NAME}] Cached filter: {remote_key}")
                return local_path
        except Exception:
            pass

    print(f"[{cfg.PC_NAME}] Downloading filter: {remote_key} -> {local_path}")
    s3.download_file(cfg._MINIO_BUCKET_NAME, remote_key, local_path)
    return local_path


def download_model_dir(experiment_id: int) -> str:
    """
    MinIOから results/{experiment_id}/ 配下のファイルをローカルキャッシュにダウンロードする。
    戻り値として、ローカルの絶対パスを返す。
    """
    s3 = get_s3_client()
    remote_prefix = _results_remote_prefix(experiment_id)
    local_dir_path = os.path.join(
        cfg.LOCAL_CACHE_DIR, RESULTS_PREFIX, str(experiment_id)
    )
    os.makedirs(local_dir_path, exist_ok=True)

    # ページネーションを使ってリモートディレクトリ内のオブジェクト一覧を取得
    paginator = s3.get_paginator("list_objects_v2")
    # page: 一度に全てのファイルリストを返すとメモリ不足になるため、ページに分けて取得
    for page in paginator.paginate(Bucket=cfg._MINIO_BUCKET_NAME, Prefix=remote_prefix):
        # Contentsがない場合はスキップ
        if "Contents" not in page:
            continue

        # Contentsの中身を取得
        # obj: ファイルの情報
        for obj in page["Contents"]:
            remote_file_path = obj["Key"]
            # ディレクトリ自体のキーはスキップ
            if remote_file_path.endswith("/"):
                continue

            relative_path = os.path.relpath(remote_file_path, remote_prefix)
            local_file_path = os.path.join(local_dir_path, relative_path)

            # ローカルキャッシュのディレクトリを作成
            os.makedirs(os.path.dirname(local_file_path), exist_ok=True)

            # --- キャッシュ判定（簡易版） ---
            # ファイルの存在とサイズが一致すれば: 既に存在する場合はダウンロードをスキップする
            # (厳密にやるなら ETag と MD5ハッシュを比較する)
            if (
                os.path.exists(local_file_path)
                and os.path.getsize(local_file_path) == obj["Size"]
            ):
                print(f"[{cfg.PC_NAME}] Cached: {remote_file_path}")
                continue

            print(
                f"[{cfg.PC_NAME}] Downloading: {remote_file_path} -> {local_file_path}"
            )
            s3.download_file(cfg._MINIO_BUCKET_NAME, remote_file_path, local_file_path)

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
            remote_file_path = os.path.join(remote_prefix, relative_path).replace(
                "\\", "/"
            )

            # コンテンツタイプ指定(MINIOで表示可能にするため)
            content_type, _ = mimetypes.guess_type(local_file_path)
            if content_type is None:
                content_type = "application/octet-stream"

            print(f"[{cfg.PC_NAME}] Uploading: {local_file_path} -> {remote_file_path}")
            # なんかエラーでるからここで生成しているけど、接続確率のオーバーヘッドがある
            s3 = get_s3_client()
            # アップロード
            s3.upload_file(
                local_file_path,
                cfg._MINIO_BUCKET_NAME,
                remote_file_path,
                ExtraArgs={"ContentType": content_type},
            )
