// バイナリクレート

use server::routes::ApiDoc;
use utoipa::OpenApi;

fn main() {
  // 綺麗にフォーマットされたJSONを生成
  let doc = ApiDoc::openapi().to_pretty_json().unwrap();

  // 標準出力にJSON文字列だけを出力する
  println!("{}", doc);

  eprintln!("openapi.json を生成しました！");
}
