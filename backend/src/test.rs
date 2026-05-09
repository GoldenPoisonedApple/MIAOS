use redis::{Client, Commands};

pub fn test() {
	let redis_client = Client::open("redis://127.0.0.1:6379").unwrap();
	let mut conn = redis_client.get_connection().unwrap();
	conn.set("key", "value").unwrap();
	let value = conn.get("key").unwrap();
	println!("value: {}", value);
}