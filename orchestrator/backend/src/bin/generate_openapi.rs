// バイナリクレート

use server::routes::ApiDoc;
use utoipa::OpenApi;
use std::fs;

fn main() {
	// 綺麗にフォーマットされたJSONを生成
	let doc = ApiDoc::openapi().to_pretty_json().unwrap();
	
	// プロジェクトのルートディレクトリに出力
	fs::write("openapi.json", doc).expect("JSONの書き込みに失敗しました");
	
	println!("openapi.json を生成しました！");
}