use axum::{
	extract::State,
	extract::Path,
	response::Response,
	body::Body,
	http::header
};
use tokio_util::io::ReaderStream;
use std::sync::Arc;
use urlencoding::decode;
use crate::services::file::StorageService;
use crate::repositories::storage::StorageRepository;
use crate::error::ServerError;

/// ファイルの取得
#[utoipa::path(
	get,
	path = "/api/files/{key}",
	responses(
		(status = 200, description = "ファイルが正常に取得された", body = Vec<u8>),
		(status = 404, description = "ファイルが見つからない"),
		(status = 500, description = "サーバー内部エラー")
	),
	tag = "Files"
)]
pub async fn get_file(
	State(service): State<Arc<StorageService<StorageRepository>>>,
	Path(key): Path<String>,
) -> Result<Response, ServerError> {
	// URLエンコードされたキーをデコード %2F -> / など
	let key = decode(&key)?;
	// オブジェクト取得
	let object = service.fetch(&key).await?;

	// 情報取得
	let content_type = object.content_type().unwrap_or("application/octet-stream").to_string();
	let content_length = object.content_length();

	// Body::from_stream は ByteStream を直接受け取れない
	// body: ByteStream -> AsyncRead -> Stream
	let stream = object.body.into_async_read();
	let body = Body::from_stream(ReaderStream::new(stream));

	let mut builder = Response::builder()
		.header(header::CONTENT_TYPE, content_type)
		.header(header::CONTENT_DISPOSITION, "inline");	// ブラウザ内表示 attachmentだとダウンロード

	if let Some(content_length) = content_length {
		builder = builder.header(header::CONTENT_LENGTH, content_length.to_string());
	}

	let response = builder.body(body).unwrap();

	Ok(response)
}
