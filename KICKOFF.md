# KICKOFF.md — `gitai` Claude Code キックオフプロンプト集

## 使い方
- フェーズ順に、該当ブロックを Claude Code に貼る。**Phase 0 を最初に。** ゲートを越えるまで次に進まない。
- 各プロンプトの冒頭で必ず `PLAN.md` を参照させる。設計判断ログ(§1)は不変条件。
- 開発ディレクトリ想定：`/Users/ryosuke/dev/gitai`（Mac mini, Claude Code MAX）。
- 言語：クライアント＝TypeScript+Vite+Capacitor、バックエンド＝Python+FastAPI。

---

## 共通プリアンブル（全フェーズの先頭に付ける）

```
あなたは gitai（擬態）の実装を担当する。まず PLAN.md を読み、特に §1 設計判断ログを
不変条件として扱うこと。以下は絶対に緩めてはならない:

[不変条件]
- 決定A: 勝利条件は素体XをターゲットYに「化けさせる」陽性課題。白紙/消す方向の設計を提案しない。
- 決定B: スコアは自前SigLIP/CLIP（決定的）のみ。LLMでスコアを出さない。
- 決定C: LLMは画像を判定しない。CLIPの判定を真実として受け取り「演じる」だけ。
- 決定性: 同一(画像bytes, pair_id, ref_version) → 必ず同一score。再採点で監査可能であること。
- 演出層はドメインの権威ゼロ。Scoringコンテキストの外に置く。
- 効率(ストローク数/時間)を核スコアに混ぜない。別ラダーに隔離する。

[DDD方針 — PLAN §2.1]
- DDDを効かせるのはバックエンドの3コンテキスト(Scoring/Puzzle/Competition)のみ。
- 推論モデルの実行はDomainに置かない。Domainの JudgeModel ポートの裏(Infrastructure)に隠す。
  Domainに推論を書くと「DDD風の手続き型コード」になる(ddd-architecture スキルの警告)。
- クライアント(TS)はDDDではない。UI/描画として書く。
- プリミティブ・オブセッション回避: Score / Percentile / Confidence / RefVersion 等はVOで包む。
- Aggregateは小さく保つ(Submission, Pair, DailyPuzzle, Leaderboard)。

[作業規律]
- 各フェーズのゲート条件を満たしたか、終了時に自己点検して報告する。
- 不確実な設計判断は勝手に決めず、PLAN の該当節を引いて確認を求める。
```

---

## Phase 0 — キルスイッチ検証（最初にこれ）

```
[共通プリアンブルを貼る]

目的: ビルドに入る前に「ゲームが数学的に成立するか」を最小コストで確かめる。
ここで失敗するなら1日で失敗させたい。UI もDBも作らない。検証スクリプトだけ。

タスク:
1. Python環境を立て、SigLIP系とCLIP(ViT-L/14, open_clip)の両方をロードできるようにする。
   ※ 私の手元で実機ベンチして本採用を決めるので、両方差し替え可能なインターフェースで書く。
2. 手作りの擬態画像セット(私が用意 or 簡易合成)を読み込む scoring harness を作る。
   各画像に (pair=(X,Y), 想定bucket) のメタを付与できる形式(JSON)。
3. 1回のスコアリングで候補集合 {Y, X, ダミー数個} に対し:
     - 温度τ付き softmax: probs = softmax([cosine(img, text_c)*TAU for c in cands])
     - Cy=P(Y), Cx=P(X)
     - raw = Cy * (1 - Cx)
   を計算。テキスト埋め込みは描画ドメインのテンプレでアンサンブル:
     ["a crude drawing of {c}", "a child's sketch of {c}", "a simple drawing of {c}"]
4. τ を {100, 50, 30, 20} でスイープし、各設定で「下手な絵 vs 上手い絵」の raw 分布が
   どれだけ割れるか(spread)を可視化する。

検証する3問(レポートで答える):
  Q1. X→Y機構は raw スコアの「幅(spread)」を生むか?
  Q2. 描画で(文字を書かずに)本当にモデルを騙せるか? 文字「BASEBALL」を書いた画像も入れて、
      それが不正に高得点を取ること(=タイポ攻撃の実在)も確認する。
  Q3. τ を下げると勾配は滑らかになり、漸進的改善がスコアに反映されるか?

go/no-go ゲート:
  代表的お題で「下手な絵と上手い絵がスコアで明確に割れる」が再現できれば go。
  割れなければ、その理由(モデル幾何の問題か、お題選びの問題か)を分析して報告。
  → これが満たせないならプロジェクトは中止候補。正直に判定すること。
```

---

## Phase 1 — 採点サービスの心臓

```
[共通プリアンブルを貼る]

目的: 決定的・監査可能なスコアリングサービスを作る。最高リスクの技術ピース。
Scoring コンテキストとして実装(PLAN §2.2)。

=== CLIPスコアサービス I/F 定義 ===
HTTP (FastAPI):
  POST /v1/score
    req:  { image_b64, pair_id, ref_version, stroke_log?: StrokeLog }
    res:  {
      score: int,                       // 0..1000, = round(1000 * percentile)
      percentile: float,                // 0..1
      raw: float,                        // Cy*(1-Cx)*ocr_factor
      confidences: { Cy: float, Cx: float, negs: float[] },
      bucket: "fooled" | "failed" | "confused",
      flags: { ocr_cheat: bool, moderation: "pass"|"flag" },
      model_version: str, template_set_id: str, tau: float,
      computed_at: iso8601
    }
    不変条件: 同一(image_b64, pair_id, ref_version) → 必ず同一 res(score/raw/percentile)。

Domain ポート(I/Fのみ。実装はInfrastructure):
  JudgeModel:
    encode_image(bytes) -> vec            # 固定クロップTTA。ランダム拡張禁止
    encode_text(label, template_set_id) -> vec   # キャッシュ
    model_version: str
  OcrScanner:
    scan(bytes) -> str[]                  # 検出テキスト

=== ペア三つ組スキーマ(凍結) ===
Pair (Aggregate Root):
  pair_id: str
  base:    { object_id, canonical_label, aliases: str[] }     # X
  target:  { object_id, canonical_label, aliases: str[] }     # Y
  hard_negatives: [ { object_id, label } ]                    # K個・凍結。提出毎に変えない
  difficulty_prior: float                                      # 非公開(候補選別専用)
  difficulty_measured: float|null                              # シード由来・公開
  template_set_id: str
  status: "candidate"|"seeded"|"active"|"retired"
SeedScores (per model_version):
  pair_id, model_version, template_set_id, tau,
  scores_sorted: float[],                                      # 昇順 raw の N個
  stats: { min, p10, p50, p90, max, mean, std }, computed_at

=== スコアリング・パイプライン(決定的・サーバー権威) ===
def score(image, pair, ref_version):
    # 1. タイポグラフィック攻撃ガード(致命傷1)
    text = ocr.scan(image)
    cheat = max(fuzzy(t, w) for t in text for w in [pair.target.label, *neg_labels])
    ocr_factor = 0.0 if cheat > TEXT_TH else 1.0      # 単語を書く=ハード0点

    # 2. 符号化(固定クロップTTA。ランダム禁止)
    img = mean(judge.encode_image(a) for a in fixed_augments(image))
    cands = [pair.target.label, pair.base.label, *neg_labels]
    txt = [judge.encode_text(c, pair.template_set_id) for c in cands]  # キャッシュ

    # 3. 温度付き softmax(問題0。τはPhase0で決めた値)
    probs = softmax([cosine(img, t) * TAU for t in txt])
    Cy, Cx = probs[idx_target], probs[idx_base]

    # 4. raw 擬態スコア
    raw = Cy * (1 - Cx) * ocr_factor

    # 5. ペアごとパーセンタイル正規化(キーストーン: 致命傷2+3を同時に殺す)
    ref = load_seed_scores(pair.pair_id, ref_version)   # ref_versionでピン留め
    p = percentile_rank(raw, ref.scores_sorted)

    # 6. 核スコアは擬態のみ(効率は別ラダーへ隔離)
    return round(1000 * p), p, raw, {Cy, Cx}

=== percentile 正規化 擬似コード ===
from bisect import bisect_left
def percentile_rank(raw, scores_sorted):   # 0..1, 決定的
    a = scores_sorted                      # 昇順
    return bisect_left(a, raw) / len(a)
# 注: t-digest等のストリーミングスケッチは使わない(精度損失・非決定性)。
#     N=数百ならソート済み生配列をそのまま持つのが正確・決定的・監査可能。

=== 決定性の制約(再採点監査の前提。全て厳守) ===
- 同一(image bytes, model_version, template_set_id, tau) → 同一 score。
- TTAは固定クロップのみ。ランダム拡張・ランダムシード依存を一切入れない。
- スコアパスは fp32(GPU fp16 は機種間で微小に非決定的になりうる)。
  または推論バックエンド+精度をシーズン内でピン留めし、途中変更しない。
- テキスト埋め込みは (label, template_set_id, model_version) でキャッシュし、ペア内で凍結。
- percentile は ref_version(= model_version + template_set_id + tau + seed_snapshot + freeze_date)
  を明示引数に取る。暗黙のグローバル状態に依存しない。
- ハードネガティブはペア定義の一部として凍結。提出毎に変えない。
- ジャッジモデル重みはシーズン内で不変。シーズン跨ぎでのみローテーション。

ゲート:
  - 同一提出を2回投げて score が完全一致することをテストで保証。
  - Phase0 の手作り画像セットを投入し、期待通りのスコア序列(上手い>下手, 文字チート=0)を確認。
```

---

## Phase 2 — お題プール基盤

```
[共通プリアンブルを貼る]

目的: 「良いお題(=シード分布の幅が広い)」を安価な漏斗で量産する。Puzzle コンテキスト。
キュレーションの漏斗(PLAN §3): N²候補 → タグ距離で絞る(無料) → 安価プレフィルタ
(1-2枚シード生成で即死棄却) → 本シード(N枚, 分布測定) → spreadで選別。

=== ObjectCatalog スキーマ === (PLAN §3 を参照)
  3群に分離: (A)ジャッジ向け / (B)難易度・キュレーション向け / (C)運用。
  色(dominant_colors)は難易度に使わない。テーマ/見栄えのみ。

=== a-priori 難易度(候補選別専用・非公開) ===
def difficulty_prior(X, Y):
    d_shape = l2(X.shape_vec - Y.shape_vec) / sqrt(5)      # 0..1 主軸
    d_sem   = (1 - cosine(emb(X.label), emb(Y.label))) / 2 # 0..1 補助
    return clamp01(
        0.55 * d_shape                  # 形状不一致が最大ドライバ
      + 0.25 * (1 - X.malleability)     # 素体が化けにくいほど難
      + 0.15 * (1 - Y.evocability)      # 標的が想起しにくいほど難
      + 0.05 * d_sem )                  # 整合性チェック程度。色は重み0
def is_plausible(X, Y):                 # ハードゲート: シルエット非互換は生成前に棄却
    return l2(X.shape_vec - Y.shape_vec)/sqrt(5) <= 0.8
# 重要: prior はあくまで候補絞り込み。プレイヤーに見せる難易度は measured(下記)を使う。

=== 測定された本物の難易度(シード分布から) ===
difficulty_measured = bucket(seed.p50)                 # 達成可能中央値が低い=難しい
is_good_puzzle      = (seed.p90 - seed.p10) >= SPREAD_FLOOR    # 幅=技術が効く=採用基準
reject_if(seed.p90 < IMPOSSIBLE_FLOOR)                 # 上手い人でも勝てない=不可能
reject_if(seed.p10 > TRIVIAL_CEILING)                  # 下手でも勝てる=技術が効かない
# 採用は「平均」でなく「分散(spread)」優先。player-facingの星評価は measured 由来。

=== LLM支援タグ付けスクリプト (tag_objects.py) ===
目的: 物体カタログの (B)群タグを Claude で下書き → 人間レビュー。手作業200個は回らない。
入力:  物体ラベルのリスト(任意で参考画像)。バッチ処理。
処理:  各物体について Claude に以下を構造化出力させる:
  プロンプト骨子:
    "次の物体について、ゲームの擬態難易度タグを推定してJSONのみで出力せよ。
     - shape_vec: [丸み, 細長さ, 平面性, 手足性, 細部密度] 各0.0..1.0
     - malleability: 0..1  (白い素体として他の物に化けやすいか。風船=0.9, 人の顔=0.1)
     - evocability: 0..1   (少ない描線で想起させやすいか。バナナ=0.9, マイナー物=0.2)
     - aliases: string[]   (OCRガード用。日英表記ゆれを含む)
     - category: food|tool|animal|vehicle|... 
     物体: {label}"
出力:  review.csv / review.json に書き出し、人間が修正できる列構成にする。
       承認フラグが立った行のみ ObjectCatalog に投入。
       source は llm_proposed → 人間承認後 human_curated に更新。

=== シード生成パイプライン(GPT画像生成を流用) ===
- ペア候補を difficulty_prior で帯フィルタ → is_plausible でハードゲート。
- 安価プレフィルタ: 各ペア 1-2枚だけ GPT で「XをYに偽装した参考画像」を生成→ Phase1採点。
  妥当試行が下限を超えなければ「不可能ペア」として棄却(本シード前に予算を守る)。
- 本シード: 通過ペアに N枚生成 → Phase1採点 → SeedScores に分布を記録。

=== シード分布 2層保存(破産しない設計の鍵) ===
SeedAsset(画像・永久保存・二度と作らない) と SeedScores(モデル毎・安価再計算) を分離。
→ シーズンでモデルを替えるとき、保存済み画像を新モデルで再エンコードするだけ。
  有料の画像生成API呼び出しゼロ。再スコア後 spread<FLOOR のペアは自動フラグ→再キュレーション。

=== DailyPuzzle 凍結(再現性) ===
DailyPuzzle: date, pair_id, ref_version(=SeedScores行+当日始点スナップショット), frozen_at
percentile は (pair_id, model_version, template_set_id, tau, date) で完全再現可能であること。

ゲート:
  - 自動漏斗を通した数十ペアで、spread>=FLOOR を満たす「良いお題」の歩留まりを実測。
  - 最初の数百ペアの歩留まり率を測ってから生成予算を組む(予算を先にコミットしない)。
```

---

## Phase 3 — クライアント最小ループ（初プレイアブル）

```
[共通プリアンブルを貼る]

目的: シングルプレイの一連ループを動かす。ランキングはまだ作らない。
スタック: TypeScript + Vite + Capacitor。描画は素のHTML5 Canvas 2D
(ペイントツールの正しいプリミティブ。Phaserはv1では使わない)。

フロー:
  お題(X→Y)表示 → 描画キャンバス(ストロークログを記録) → 提出
   → /v1/score 呼び出し → リビール演出 → シェアカード生成。

=== リビール演出(切り抜きを内蔵する。PLAN §1演出キーストーン) ===
- サスペンス→ペイオフ構造: 絵を表示 → 「AIに見せています…」スキャン演出1-2秒(意図的アニメ。
  CLIPは高速なので溜めは演出) → 判定をドロップ → スコアを叩き込む。数字を即出さない。
- 勝ちも負けも両方笑える: 勝ち=「ゴミ絵を高級品と誤認させた」/ 負け=辛辣な酷評。
- bucket(fooled/failed/confused)で演出とコメントのトーンを出し分ける。

=== テンプレバンク スキーマ(演出Layer1・LLM呼び出しゼロ) ===
TemplateBank:
  template_id: str
  bucket: "fooled" | "failed" | "confused"
  locale: str                       # 機械翻訳しない。ロケール毎にネイティブ作成
  slots: str                        # "これは…{Y}ですね。間違いなく。{Cy}%、{Y}です。" 等
                                    #  プレースホルダ {Y}{X}{Cy}{score} を埋める
  weight: float                     # 乱択の重み
  mood: "smug"|"delighted"|"suspicious"|"exasperated"   # マスコット表情の出し分け
参照: (bucket, locale) → バリアントを weight で乱択。1キー複数バリアントで缶詰感を消す。
注: これは事前計算キャッシュであり最大のコストレバー。大多数のプレイはここで完結し、
    LLM Vision(Phase5)はヒーロー/オンデマンドのみに温存する。

=== シェアカード(Pillow+Noto Sans CJK JP を流用。殺し技) ===
- リビール時に 9:16 縦カードを自動合成: before(X)→after, 鑑定士の一言(大きな引用),
  スコア, ハンドル, mood表情, そして「今日のお題: XをYに化けさせろ」。
- ワンタップ共有。お題をカードに埋めて「見た人=やりたくなる人」のループを閉じる。
- 描画リプレイ(タイムラプス): ストロークログを早回し再生。満足感+共有性+不正検証を兼ねる。

ゲート:
  - 自分(と数人)が「もう一回やりたい」と感じるか。
    感じなければコアループの面白さの問題 → 設計(PLAN §1)に戻る。正直に判定。
```

---

## Phase 4 — 非同期競争

```
[共通プリアンブルを貼る]

目的: netcodeなしで競争を成立させる。Competition コンテキスト。

- デイリーチャレンジ・リーダーボードが背骨: 全員同じペア → スコア直接比較 → 毎日リセット
  (FOMO・習慣化)。同一お題でシェアカードが揃いミーム密度が上がる。free-for-allにしない。
- ゴースト: 現1位の絵+判定を「これを超えろ」として表示。リプレイと競争=netcode不要。
- 複数ラダー(全員に勝ち場): グローバル・デイリー / フレンド・デイリー(保持&拡散の核) /
  効率ラダー(最少ストロークでAIを騙す。核スコアと別軸) / 「一番面白い」ラダー(人間投票)。
- 流動性のブートストラップ(PLAN R1 = 存在的リスク): シードゴーストを再利用、
  パーセンタイル/上位%表示は少人数でも機能、シェアカード→招待を主成長ループに。

=== 不正対策(ランク戦の必須要件) ===
- サーバー権威スコアリング(クライアントは自スコアを申告しない)。
- ストロークログのリプレイ検証: 最終画像がストローク列から再現できなければ拒否。
  → ランク戦の画像ペーストチートをこれで殺す。
- ピン留めモデルの決定性により、同じ提出はサーバーで同一に再採点でき監査可能。
- レート制限。
- 正直: web/Capacitorクライアントで本気のストローク偽装は完全には防げない。
  リプレイ検証で大幅に上げる。カジュアル帯ならこれで十分、と割り切る。

- 保持ループ: デイリーリセット + 「フレンドにスコアを抜かれた」プッシュ(Capacitor通知)。

ゲート:
  - 招待→新規の成長係数が立つか(R1)。ここが生死の本丸。立たなければ撤退も検討。
```

---

## Phase 5 — 演出強化 & 収益化

```
[共通プリアンブルを貼る]

目的: 鑑定士LLMコメント層・モデレーション・収益化・シーズン制。演出はドメインの外。

=== 鑑定士 人格プロンプト(Layer2・LLM Vision) ===
人格: 自信過剰な美術鑑定士「鑑定士」。固定の名前付きマスコット=ブランド装置=拡散資産。
システムプロンプト骨子:
  【絶対規則】
  - 判定は確定済み。あなたは覆さない・再判定しない。入力 verdict が「真実」。
  - verdict が「{Y}・確信度{Cy}%」なら、画像が明らかに{X}でも{Y}だと信じきって語る。
    この確信が芸(決定C)。
  - 1〜2文・平文・記号禁止(カードの帯に乗る長さ)。
  - 茶化す対象は「絵」だけ。描いた人間の人格・知能・属性に一切触れない。
  - 出力JSON: {"line": "...", "mood": "smug|delighted|suspicious|exasperated"}
  【トーン分岐】bucketで決定
  - fooled : {Y}を心から鑑賞・絶賛。だまされた自覚ゼロ。
  - failed : 「{X}が{Y}の振りをしている」と上品に皮肉る。辛辣だが下品でない。
  - confused: {X}とも{Y}ともつかず、威厳を保とうと空回りする。
  【入力】verdict, X, Y, Cy, Cx, bucket, image
  【few-shot】各bucket 2-3例(確信して間違える例を厚めに)
注:
  - コメントは高温度OK(スコアの決定性とは対比。同じ絵が別コメントでもスコア不変)。
  - ただしヒーロー投稿のコメントは鋳造後に凍結(その切り抜きの正典)。
  - ロケール毎に人格をネイティブ再設計。機械翻訳不可。

=== 安全フィルタ(R5) ===
(a) プレイヤーの絵: LLMに届く前に画像モデレーション分類器でゲート(NSFW/暴力/ヘイト記号)。
    フラグ → LLM呼ばない・公開カード生成しない・公開ラダーから除外・安全フォールバック。
    ※採点/OCRパスの前段にも置く。不適切画像はそもそもランキングに載せない。
(b) LLM出力: 出力後フィルタでスラー/ポリシー違反をスキャン→ テンプレバンクにフォールバック。
最高リスク面はシェアカード(拡散する)。カード生成自体をモデレーション通過の前提条件にする。

=== 予算ガバナ(R6・破産しない設計のこの層への適用) ===
- daily_llm_spend_cap: 1日あたりLLM呼び出し総額のハード上限。
- Layer2リクエスト毎に当日spendをチェック。上限超過 → その日の残りはヒーローも
  テンプレバンクに「優雅に劣化」。ハードエラー・請求暴走には絶対しない。
- 無料枠: ユーザーあたり「鑑定士に見せる」オンデマンド N回/日。プレミアムは無制限。
  → 収益化(プレミアム=無制限)とコスト上限(無料枠制限)を同時に満たす。

=== ヒーロー投稿の判定基準(いつ高価なLLMを払うか) ===
- 主基準: Phase2で既に計算済みのパーセンタイル p を流用(タダでそこにある)。p>=0.95でLayer2。
- オンデマンド: 非ヒーローでもプレイヤーがボタンで自分で発火(無料枠/プレミアム)。
  → 派手な大失敗(最高スコアではないが最高に面白い)の受け皿。
- 退化ガード: ヒーロー資格 = (p>=0.95) AND moderation_pass AND NOT ocr_cheat。
  チート投稿・不適切投稿をフィーチャーしない。
- ヒーローコメントは初回鋳造後に content-hash でキャッシュ・凍結。
- レイテンシ: スコアのリビールをLLMでブロックしない。テンプレで即リビール、
  ヒーローの画像特化文は鋳造でき次第カードに後から差し込む。

=== 収益化 & シーズン制 ===
- F2P + デイリー回数制限。プレミアム(練習無制限・追加試行・コスメ・広告なし・鑑定士無制限)。
- 報酬はコスメのみ(パレット, 鑑定士スキン)。リアルマネー取引・UGCマーケットは作らない(面を綺麗に)。
- シーズン制(2-4週): ジャッジモデルをピン留め → シーズン終了でリーダーボードをリセット&再スコア。
  運用上の必然(モデル更新)を再エンゲージとチート無効化に転換(R2/R4)。
  「シーズン2 = 新ジャッジ = 新メタ」。

ゲート:
  - バズ規模を模した負荷で、LLM課金が日次上限で頭打ちになり優雅に劣化することを確認。
    請求が青天井にならないことを必ずテストで保証。
```

---

## 最後に — Phase 0 を飛ばさないこと

このゲームが成立するかは Phase 0 の1点（お題がスコアの幅を生むか）で決まる。
UIもDBも作る前に、まずスクリプトでそれを確かめる。**1日で死ぬなら、1日で死なせる。**
それが本家の教訓「自分の資産を流用して速く出す/速く確かめる」の、検証フェーズへの適用。
