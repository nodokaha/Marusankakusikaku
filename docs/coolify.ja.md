# Coolify で BasisMultiWorld をデプロイする

この構成は Coolify の Docker Compose リソース1つで複数の Basis ワールドを運用します。
Basis サーバーのコンテナ1つが worlds.conf に記載された全ワールドを起動・監視し、
必要に応じて Caddy が Coolify Proxy の背後で HTTP/WebSocket をワールドごとに振り分けます。HTTPS は Coolify Proxy が終端します。従来の configure.sh と生成 Compose による
通常の Docker Compose 運用も引き続き利用できます。

## 1. Coolify リソースを作成

1. Coolify で https://github.com/nodokaha/Marusankakusikaku から Docker Compose リソースを作成します。
2. Compose ファイルのパスを coolify/compose.yaml にします。
3. 次節の環境変数を登録します。
4. Web クライアント / WSS を使う場合は COMPOSE_PROFILES=web と WEB_PLAYERS=yes を設定します。
   UDP のネイティブクライアントだけなら profile は不要です。
5. Web profile を有効にした場合、Coolify の caddy サービスにドメインを割り当て、内部ポートを 80 にします。
   DNS_ZONE、ハブのスラッグ、DNS_HOST.DNS_ZONE、および各ワールドのスラッグのドメインを登録してください。
   HTTPS は Coolify Proxy が担当し、Caddy が HTTP/WebSocket を各 Basis ワールドへ振り分けます。
6. Deploy します。初回ビルドでは Basis と WebSocket transport のソース取得・コンパイルを行います。
   数分かかる場合があり、RAM 約 1.5 GB、空きディスク約 2 GB が必要です。

ワールドごとに Coolify リソースを作る必要はありません。ヘルスチェック用ポートや
ダッシュボード用ポートは外部公開しないでください。

## 2. 環境変数

.env.example を基準に Coolify の Environment Variables に登録してください。最低限必要な項目：

| 変数 | 例 | 用途 |
| --- | --- | --- |
| BASIS_REF | 2f5b3e106ea10a1dc96b208d000428a335ef7c6c | Basis 上流コミット |
| WEBSOCKET_REF | 62a4468432eb82c78ac744a7e78fca4bb91f7c8a | WebSocket transport コミット |
| CDN_BASE | https://cdn.example.com/basis | .BEE の相対 URL のベース |
| UNLOCK_PASSWORD | secret | バンドルのパスワード |
| BASIS_FIRST_ADMIN | did:key:... | 初回起動時の管理者 DID |
| WORLD_PORT_START | 4296 | UDP 公開ポート範囲の開始 |
| WORLD_PORT_END | 4298 | UDP 公開ポート範囲の終了 |

参加パスワードは HUB_PASSWORD、FOREST_PASSWORD のように設定します。
任意で <SLUG>_MOTD、<SLUG>_PEER_LIMIT、<SLUG>_API_KEY も指定できます。
スラッグは大文字化し、ハイフンを _ に置き換えた名前を使います。
worlds.conf の全ポートが公開範囲内に入るようにしてください。

Web クライアントを使う場合は追加で以下を設定します。

- WEB_PLAYERS=yes
- DNS_ZONE=worlds.example.com（実際にこのサーバーを向くドメイン）
- DNS_HOST=vm1（単一の DNS ラベル。既定値は vm1）
- 任意で WEB_CLIENT_URL=https://play.worlds.example.com

HTTPS 証明書は Coolify Proxy が自動取得・更新します。この Compose からホストの 80/443 を公開しないでください。
WSS は Proxy 経由で通常の HTTPS ポート 443 を使い、ゲーム通信の UDP は Basis コンテナに直接転送されます。
既定の 172.30.42.0/24 が他の Docker ネットワークと重複する場合は PROXY_NET を変更してください。Caddy 経由で実際の接続元 IP を Basis に渡す場合は COOLIFY_PROXY_NET に Coolify Proxy の Docker ネットワーク CIDR を設定してください。

## 3. ワールド設定

デプロイ前にリポジトリの worlds.conf を編集します。1行目がハブで、UDP 4296 を推奨します。

```text
hub      4296   Hub.BEE       My Hub
forest   4297   Forest.BEE    Forest Walk
city     4298   City.BEE      City at Night
```

バンドルは HTTPS の完全な URL、または CDN_BASE からの相対パスを指定できます。
ワールド設定、プレイヤーセーブ、サーバーに保存したプロップ、Default Library は
basis-data 名前付きボリュームの /data/worlds/<slug> に保存されます。

Basis コンテナは設定したポート範囲の UDP を公開します。ファイアウォールでは使用する UDP ポートだけを許可してください。
ネイティブクライアントには従来どおり DNS SRV レコードが必要です。dns-records.sh で BIND 形式のレコードを生成してください。

## 4. 永続化と更新

Coolify の名前付きボリュームは再デプロイ後も保持されます。

- basis-data：ワールド設定・セーブ・保存済みプロップ・Default Library
- caddy-data / caddy-state：Caddy の状態（TLS 証明書は Coolify Proxy が管理）

各ボリューム、.env、worlds.conf をバックアップしてください。
BASIS_REF または WEBSOCKET_REF の変更時はイメージを再ビルドします。
worlds.conf や実行時環境変数の変更時はサービスを再デプロイしてください。

## 制限事項

- この Coolify プリセットでは1つの Basis コンテナ内で全ワールドを実行します。
  いずれかのワールドが異常終了すると、現在は全ワールドを停止します。
- 既存 Compose のワールド別ダッシュボードコンテナは、このプリセットには含めていません。
  ダッシュボードが必要な場合は従来の configure.sh による構成を利用してください。
- WebSocket transport はイメージに含まれます。Caddy を使うには WEB_PLAYERS=yes と Compose profile web の両方が必要です。Coolify で caddy サービスの内部ポート 80 に各ドメインを割り当ててください。TLS は Coolify Proxy が 443 で終端するため、Caddy の 80/443 をホストに公開しません。
