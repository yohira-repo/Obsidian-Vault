---
title: "クラウド代ゼロ円！？LocalStackで爆速テスト環境を手に入れる方法"
source: "https://zenn.dev/churadata/articles/ca2f61b28cf89e"
author:
published: 2025-01-01
created: 2026-09-08
description:
tags:
  - "clippings"
---
30

8

## 概要

この記事を読む対象者:  
「AWSを使って開発したいけど、コストや設定が気になる…」と悩んでいるエンジニア

この記事の内容:  
LocalStackの概要や歴史、インストールから基本操作まで、手を動かしながら学べる実践ガイドをお届けします

この記事を読んで分かること:  
LocalStackを活用してAWSサービスをローカルでエミュレーションし、 **コスト抑え効率よくテスト環境を構築する方法** が身につきます！

## 序説

「AWSは便利だけど、テストするだけなのにお金がかかるのはちょっと…」そんな経験、ありませんか？

本番環境でいきなり試すのはリスクが高く、設定ミスで予算オーバーになることも。

そんな悩みを解決してくれるのが **LocalStack** です！

LocalStackを使えば、AWSの主要サービスをローカルでそっくり再現できるため、コストを気にせず高速に開発・テストが可能になります。

この記事では、インストール手順や具体的な操作方法を実践形式でご紹介します。AWS開発をスムーズに進めたい方は、ぜひ最後まで読んでみてください！

## LocalStack

## localstackとは

LocalStackの概要  
LocalStackは、AWSのサービスをローカル環境でシミュレーションできるオープンソースツールです。  
特徴  
1\. コストゼロで開発できる！ - クラウド使用料を気にせず、ローカルで自由に検証可能。  
2\. ネットワーク遅延なし！ - 外部通信を必要としないため、結果確認が超高速。  
3\. セットアップ簡単！ - Dockerを使って数分で環境構築完了。  
4\. AWSの主要機能をサポート！ - S3、DynamoDB、Lambda、SQSなどを再現。

使いどころ  
• 機能検証：コードがちゃんと動くか、まずはローカルでチェック！  
• CI/CDパイプライン：テスト環境を組み込み、自動化を強化。  
• オフライン開発：インターネットがない場所でも動作検証可能。

## LocalStackの仕組みとアーキテクチャ

![](https://static.zenn.studio/user-upload/9b51a960654b-20250101.png)

1. 構成要素
	1. Docker-compose  
		• LocalStackの設定とサービス起動を管理。
		2. Persistent State  
		• テストデータや設定を保存し、再利用可能にするストレージ。
		3. LocalStack  
		• AWSサービスをエミュレートし、APIリクエストを処理。
		4. Docker Demon  
		• コンテナの起動・管理を行い、LocalStackやサービスを動かす基盤。
		5. S3 (エミュレーション)  
		• S3の動作を模倣し、データ保存や取得をシミュレート。
2. 動作の流れ
	1. 設定の読み込み  
		• Docker-composeがLocalStackに設定を渡す。
		2. サービス起動  
		• LocalStackがDocker Demonを通じてAWSサービスを起動。
		3. APIリクエスト処理  
		• ユーザーからのAPIリクエストを受け、サービスがデータを操作。
		4. データの永続化  
		• Persistent Stateがデータを保存し、テスト環境を維持。

## localstackの歴史

LocalStackの歴史

LocalStackは、AWSのクラウドサービスをローカル環境でシミュレーションするために開発されました。

#### 誕生の背景

LocalStackは、2016年に ATLAS ElecSystems社 から生まれました。最初はAWS LambdaやDynamoDBをローカルでテストするための小さなツールだったのです。

クラウド時代の拡大とともに、「テストのたびにクラウド料金がかかるのは困る！」という悩みが増え、LocalStackはその解決策として進化していきました。

課題解決ポイント

- コスト削減：クラウドに接続しなくても、無料で動作確認できる！
- オフライン対応：ネットワーク不要でいつでもテストできる！
- CI/CD強化：自動テスト環境に組み込みやすく、開発効率アップ！

#### 成長と拡張

- 2017年：GitHubでオープンソース化され、開発者コミュニティが成長。
- 2018年：Dockerを使った簡単なセットアップが可能に！
- 2020年：Pro版登場。対応サービスが増え、商用サポートも強化。
- 2023年：大規模アップデートでサーバーレス機能やCI/CD統合がさらに充実。

#### 現在の役割

LocalStackは今や、AWSのローカルエミュレーションツールとして広く使われ、DevOpsやCI/CD環境の標準ツールとなっています。

## 手順

## 必要なツールのインストール

まず、必要なツールをインストールします。

以下のコマンドでLocalStackのリポジトリをクローンします。

```
git clone https://github.com/localstack/localstack.git
```

AWS CLIとJSONパーサーのjqをインストールします。

```
brew install awscli
brew install jq
```

次に、Dockerを起動してLocalStackをセットアップします。

LocalStackディレクトリに移動し、Docker Composeを実行:

```
cd localstack
docker-compose up -d
```

起動状態の確認:  
LocalStackのヘルスチェックエンドポイントにアクセスし、起動状態を確認します。

```
curl -s “http://127.0.0.1:4566/_localstack/health” | jq .
```

出力例:

```
{
“services”: {
“s3”: “running”,
“dynamodb”: “running”,
“lambda”: “running”,
“sns”: “running”,
“sqs”: “running”
},
“status”: “running”
}
```

すべてのサービスが “running” になっていることを確認してください。  
これでLocalStackが正しく動作していることを確認できました。

## ファイルの準備

まず、アップロードするファイルを作成します。  
`vi test.txt`  
エディタが開くので、任意のテキストを入力し保存します。

例:`Hello LocalStack!`  
エディタを終了してファイルを保存したら、作成を確認します。

出力:`Hello LocalStack!`

## S3バケットの作成

LocalStack上でS3バケットを作成します。

```
awslocal s3 mb s3://localstack-bucket
```

作成したバケットの一覧を確認します。

```
awslocal s3 ls
```

出力例:

```
2024-01-01 12:34:56 localstack-bucket
```

## ファイルのアップロード

作成したテキストファイルをバケットにアップロードします。

```
awslocal s3 cp ./test.txt s3://localstack-bucket/
```

アップロードしたファイルを確認します。

```
awslocal s3 ls s3://localstack-bucket/
```

出力例:

```
2024-01-01 12:35:00 19 test.txt
```

## ファイルのダウンロードと確認

アップロードしたファイルをローカルにダウンロードして内容を確認します。

```
awslocal s3 cp s3://localstack-bucket/test.txt ./downloaded.txt
```

ダウンロードしたファイルの中身を確認します。

```
cat downloaded.txt
```

出力:

```
Hello LocalStack!
```

## ファイルの削除

不要になったファイルをS3バケットから削除します。

```
awslocal s3 rm s3://localstack-bucket/test.txt
```

削除されたことを確認します。

```
awslocal s3 ls s3://localstack-bucket/
```

## バケットの削除

バケット自体も削除する場合は、以下のコマンドを実行します。

```
awslocal s3 rb s3://localstack-bucket –force
```

## ハマったこと

## pipとbrewを使う

#### エラー内容

```
$ awslocal s3 mb s3://localstack-bucket
Traceback (most recent call last):
  File "/Users/k-nakata/Documents/Git/localstack/.venv/bin/aws", line 5, in <module>
    from aws.main import main
  File "/Users/k-nakata/Documents/Git/localstack/.venv/lib/python3.11/site-packages/aws/main.py", line 23
    print '%(name)s: %(endpoint)s' % {
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
SyntaxError: Missing parentheses in call to 'print'. Did you mean print(...)?
```

#### 原因

このエラーは、Python 2.x向けに記述されたコードを、Python 3.xで実行しようとしたことによるものです。  
print文がPython 3では関数化されているため、print(...)の形式にしなければなりません。

#### 解決方法

仮想環境を一度解除します。  
システム環境にPython 3対応のAWS CLIをインストールします。

```
deactivate
brew install awscli
```

## jqのインストール

#### エラー内容

```
$ curl -s "http://127.0.0.1:4566/health" | jq .
zsh: command not found: jq
```

#### 原因

jqはJSONデータを扱うためのコマンドラインツールですが、インストールされていないためにエラーが発生しました。

#### 解決方法

jqをインストールします。  
コマンドの再実行で状態確認します。

```
brew install jq
curl -s "http://127.0.0.1:4566/health" | jq .
```

正常な出力例:

```
{
  "services": {
    "s3": "running",
    "dynamodb": "running",
    "lambda": "running",
    "sns": "running",
    "sqs": "running"
  },
  "status": "running"
}
```

## 結言

この記事を通じて、LocalStackの概要から歴史、インストール手順、具体的な操作例までを一通り紹介しました。

LocalStackは、AWSサービスをローカル環境で手軽にエミュレーションできる便利なツールです。これにより、クラウドコストを気にせず高速に開発・テストを進めることができるようになります。

また、エラーに直面した際の対処法も紹介したので、セットアップや運用時に役立てていただければと思います。

実際に手を動かして試すことで、LocalStackの強力さや便利さを実感できるはずです。AWS開発をもっと効率的に進めたい方は、LocalStackをぜひ活用してみてください！

## 参考

<iframe src="https://embed.zenn.studio/card#zenn-embedded__819a5876fc183" frameborder="0"></iframe>

8