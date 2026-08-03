
kubectl get secret google-api-credentials-new -n alphasys -o json | jq -r '.data["credentials.json"]' | base64 --decode

`kubectl get secret -o yaml` で出力したマニフェストファイルを編集して新しく別名で作成する場合、**「余分なメタデータ（システムが自動付与する情報）」が含まれていること**がエラーの原因になっています。

---
> マスターパスワードもローテーションしたいです。

マスター（管理者）アカウントのパスワード自体をローテーションする場合は、**「2つの別々なマスターシークレットを作成し、交互にローテーションさせる」** という特殊な MultiUser（ダブルユーザー）構成を組む必要があります。

## 💡 なぜ「シングル」ではダメで、「ダブル」が必要なのか？

- **SingleUser（1つのマスターシークレットのみ）** Lambda 自身が「今更新しようとしているマスターパスワード」を使って DB にログインし、自分自身のパスワードを変更します。ネットワークの瞬断や処理の失敗が起きると **DB にログインできなくなり、ローテーションが詰んで（ロックアウトされて）しまうリスク** が高くなります。
    
- **MultiUser（2つのマスターアカウントを交互に使用）** マスターアカウントを **2つ（例: `master_a` と `master_b`）** 作成します。 `master_a` のローテーションを行う際は、**`master_b` の資格情報を使って DB にログインし、`master_a` のパスワードを変更する** ため、非常に安全で確実にローテーションが行えます。




## 付録A. 段階デプロイ・ランブック（初期構築 / 全体作り直し時）
### ゲート② alphadb の publish（DB を alphadb 一元化後は必須）


MacBook-Air:alphadb yohira$ aws codeartifact list-package-versions \
>   --domain alphacmc --domain-owner 570024666076 --repository alphadb-npm \
>   --package alphadb --format npm --region ap-northeast-1 --profile stg

An error occurred (ResourceNotFoundException) when calling the ListPackageVersions operation: The npm package 'alphadb' does not exist in repository 'alphadb-npm'.

ns-1394.awsdns-46.org.  
ns-5.awsdns-00.com.  
ns-1689.awsdns-19.co.uk.  
ns-845.awsdns-41.net.
