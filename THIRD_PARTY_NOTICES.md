### rusty-celery
orchestrator/backend/libs/rusty-celery/

This project includes code derived from [rusty-celery](https://github.com/rusty-celery/rusty-celery),
licensed under the Apache License 2.0.

The following files were modified in 2026 to maintain compatibility with current Rust toolchains
and Python Celery interoperability:

| File | Summary |
|------|---------|
| `celery-codegen/src/task.rs` | Moved `impl Task` to module scope to avoid `non_local_definitions` on modern rustc; replaced the dummy `const _: () = { ... }` wrapper with a fully-qualified `async_trait` attribute. |
| `src/broker/redis.rs` | Added explicit type parameters to `query_async` in `remove_task` and `close` where the compiler could not infer return types. |
| `src/protocol/mod.rs` | When `delivery_info` is absent, emit a default object with an `exchange` key instead of `null`, matching Python Celery's expectations. |
| `src/task/mod.rs` | Replaced deprecated `NaiveDateTime::from_timestamp_opt` with `DateTime::<Utc>::from_timestamp` in `retry_with_countdown` and `retry_eta`. |

- Original license: [Apache License 2.0](orchestrator/backend/libs/rusty-celery/LICENSE)
