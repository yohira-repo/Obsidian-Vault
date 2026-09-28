# Spring Boot (Gradle) + PostgreSQL Dev Containers 環境構築手順

VSCodeの **Dev Containers** 拡張機能を使用し、**Spring Boot (Gradle)** と **PostgreSQL** の開発環境をマルチコンテナ構成で構築するための設定一式です。

---

## 📂 ディレクトリ構成

プロジェクトのルートディレクトリに以下の配置でファイルを構成します。

```text
(プロジェクトルート)
├── .devcontainer/
│   ├── devcontainer.json
│   └── compose.yaml
└── src/
    └── main/
        └── resources/
            └── application.properties
```

---

## 📄 設定ファイル一覧

### 1. `.devcontainer/compose.yaml`
Spring Bootを動かすアプリ用コンテナ（`app`）と、データベース用コンテナ（`db`）の2つを定義します。

```yaml
services:
  app:
    # Java 21 と Gradle がプリインストールされた Microsoft 公式イメージ
    image: ://microsoft.com
    volumes:
      # ホストのファイルをコンテナ内にマウント
      - ..:/workspace:cached
    # バックグラウンドでコンテナを維持する設定
    command: /bin/sh -c "while sleep 1000; do :; done"
    # dbコンテナが起動した後に立ち上げる設定
    depends_on:
      - db

  db:
    image: postgres:16-alpine
    restart: always
    environment:
      POSTGRES_USER: devuser
      POSTGRES_PASSWORD: devpassword
      POSTGRES_DB: devdb
    ports:
      - "5432:5432"
    volumes:
      # データを永続化するためのボリューム
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

### 2. `.devcontainer/devcontainer.json`
VSCodeから `app` コンテナに接続し、Java/Spring Bootの開発に必要な拡張機能を自動インストールする設定です。

```json
{
  "name": "Spring Boot & PostgreSQL (Gradle)",
  "dockerComposeFile": "compose.yaml",
  "service": "app",
  "workspaceFolder": "/workspace",
  
  // コンテナ内で自動インストールするVSCode拡張機能
  "customizations": {
    "vscode": {
      "extensions": [
        "vscjava.vscode-java-pack",               // Java開発ツールパック
        "vmware.vscode-spring-boot-dashboard",    // Spring Boot ダッシュボード
        "pivotal.vscode-boot-dev-pack",           // Spring Boot 拡張パック
        "mtxr.sqltools",                          // DB閲覧ツール本体
        "mtxr.sqltools-driver-pg"                 // SQLTools用PostgreSQLドライバ
      ]
    }
  },
  
  // Spring Boot (8080) のポートをローカルからアクセス可能にする
  "forwardPorts":,
  
  "remoteUser": "vscode"
}
```

### 3. `src/main/resources/application.properties`
Spring BootからPostgreSQLへ接続するための設定です。
ホスト名部分には、localhostではなく **`compose.yaml` で定義したサービス名（`db`）** を指定します。

```properties
spring.application.name=demo
spring.datasource.url=jdbc:postgresql://db:5432/devdb
spring.datasource.username=devuser
spring.datasource.password=devpassword
spring.datasource.driver-class-name=org.postgresql.Driver

# JPA/Hibernateの設定（起動時にテーブルを自動生成・更新）
spring.jpa.hibernate.ddl-auto=update
spring.jpa.show-sql=true
```
*(※ `build.gradle` の `dependencies` に `implementation 'org.postgresql:postgresql'` が含まれていることを確認してください)*

---

## 🚀 起動・開発手順

1. **プロジェクトを開く**
   VSCodeで上記ファイルを配置したプロジェクトルートフォルダを開きます。
2. **コンテナのビルドと接続**
   `Ctrl + Shift + P`（Macは `Cmd + Shift + P`）でコマンドパレットを開き、 **`Dev Containers: Reopen in Container`** を選択します。
3. **アプリケーションの起動**
   コンテナへの接続完了後、VSCode内のターミナルを開き、以下のコマンドで Spring Boot を起動します。
   ```bash
   ./gradlew bootRun
   ```
