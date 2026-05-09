

pub fn app_routes(app: Router) -> Router {
	Router::new()
	.route("/experiments", get(get_experiments))
}