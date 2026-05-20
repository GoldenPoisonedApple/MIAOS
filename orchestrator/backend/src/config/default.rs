use crate::entities::experiment::MiaMethod;

/// 実験名のデフォルト値
pub const EXPERIMENT_NAME: &str = "default_experiment";
/// 備考のデフォルト値
pub const EXPERIMENT_NOTES: Option<String> = None;
/// 攻撃手法
pub const MIA_METHOD: MiaMethod = MiaMethod::OfflineLira;

/// ターゲットモデルを読み込むかどうか
pub const LOAD_TARGET_MODEL: bool = false;
/// シャドーモデルを読み込むかどうか
pub const LOAD_SHADOW_MODEL: bool = false;
/// 攻撃モデルを読み込むかどうか
pub const LOAD_ATTACK_MODEL: bool = false;
/// シャドーモデルの数
pub const NUM_SHADOW_MODELS: i32 = 100;
/// クラス数
pub const NUM_CLASSES: i32 = 100;
/// バッチサイズ
pub const BATCH_SIZE: i32 = 256;
/// 最大エポック数
pub const MAX_EPOCHS: i32 = 200;
/// 攻撃モデルのエポック数
pub const ATTACK_MODEL_EPOCHS: i32 = 10;
/// データロードに使用するサブプロセス数
pub const NUM_WORKERS: i32 = 0;
// データセットの数
/// 各モデルの訓練データとテストデータは重複無し、同サイズ
/// → メンバと非メンバを同数にすることでBaseを50%にする
/// → ターゲットとシャドーでの数を同数にすることで、挙動を近づける: 類似したデータレコードで訓練された類似のモデルは同様に振る舞う
/// ターゲットモデルとシャドーモデルのデータプールは重複無し → 最悪ケースを想定
/// シャドーモデル間のデータセットは重複許容
pub const TARGET_TRAIN_SIZE: i32 = 10520;
pub const TARGET_TEST_SIZE: i32 = 10520;
pub const SHADOW_TRAIN_SIZE: i32 = 10520;
pub const SHADOW_TEST_SIZE: i32 = 10520;
/// シード値
pub const SEED: i32 = 42;
