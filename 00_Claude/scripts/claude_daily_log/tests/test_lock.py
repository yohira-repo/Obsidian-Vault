import ast
import os
import tempfile
import threading
import time
import unittest

import cli


class GuardedFcntlImportTest(unittest.TestCase):
    """D: import fcntl はガードされているべき（Windows で ModuleNotFoundError を起こさない）。"""

    def test_fcntl_import_is_guarded_by_try_except_importerror(self):
        source_path = os.path.join(os.path.dirname(os.path.abspath(cli.__file__)), "cli.py")
        with open(source_path, encoding="utf-8") as handle:
            tree = ast.parse(handle.read())

        top_level_imports = [
            node for node in tree.body
            if isinstance(node, ast.Import) and any(alias.name == "fcntl" for alias in node.names)
        ]
        self.assertEqual(
            top_level_imports, [],
            "import fcntl がガードなしでモジュールトップレベルに置かれている（Windows で起動不能になる）",
        )

        guarded = False
        for node in tree.body:
            if not isinstance(node, ast.Try):
                continue
            imports_fcntl = any(
                isinstance(stmt, ast.Import) and any(alias.name == "fcntl" for alias in stmt.names)
                for stmt in node.body
            )
            if not imports_fcntl:
                continue
            for handler in node.handlers:
                type_name = handler.type.id if isinstance(handler.type, ast.Name) else None
                if type_name == "ImportError":
                    guarded = True
        self.assertTrue(guarded, "import fcntl は try/except ImportError で保護されているべき")


class LockRetryTest(unittest.TestCase):
    """F: ロックが競合している間は数回リトライしてから諦める。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._orig_lock = cli.LOCK_PATH
        self._orig_delay = cli.LOCK_RETRY_DELAY_SECONDS
        self._orig_attempts = cli.LOCK_RETRY_ATTEMPTS
        cli.LOCK_PATH = os.path.join(self.tmp.name, "cache", "claude_daily_log.lock")
        cli.LOCK_RETRY_DELAY_SECONDS = 0.05
        cli.LOCK_RETRY_ATTEMPTS = 8  # 合計待ち時間 ~0.35s（テストを速くするため既定値より短縮）

    def tearDown(self):
        cli.LOCK_PATH = self._orig_lock
        cli.LOCK_RETRY_DELAY_SECONDS = self._orig_delay
        cli.LOCK_RETRY_ATTEMPTS = self._orig_attempts
        self.tmp.cleanup()

    @unittest.skipUnless(cli.fcntl is not None, "fcntl 前提のテスト（POSIX 専用）")
    def test_retries_until_other_holder_releases_lock(self):
        os.makedirs(os.path.dirname(cli.LOCK_PATH), exist_ok=True)
        holder = open(cli.LOCK_PATH, "w")
        cli.fcntl.flock(holder, cli.fcntl.LOCK_EX | cli.fcntl.LOCK_NB)

        def release_soon():
            time.sleep(0.15)
            cli.fcntl.flock(holder, cli.fcntl.LOCK_UN)
            holder.close()

        thread = threading.Thread(target=release_soon)
        thread.start()
        try:
            handle = cli.acquire_lock()
        finally:
            thread.join()

        self.assertIsNotNone(handle, "他プロセスの解放後、リトライで取得できるはず")
        handle.close()


class PortableLockFallbackTest(unittest.TestCase):
    """D: fcntl が無い環境（Windows）向けフォールバックが相互排他として機能する。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._orig_lock = cli.LOCK_PATH
        self._orig_fcntl = cli.fcntl
        self._orig_delay = cli.LOCK_RETRY_DELAY_SECONDS
        self._orig_attempts = cli.LOCK_RETRY_ATTEMPTS
        cli.LOCK_PATH = os.path.join(self.tmp.name, "cache", "claude_daily_log.lock")
        cli.fcntl = None  # fcntl が無い環境をシミュレート
        cli.LOCK_RETRY_DELAY_SECONDS = 0.02
        cli.LOCK_RETRY_ATTEMPTS = 3

    def tearDown(self):
        cli.LOCK_PATH = self._orig_lock
        cli.fcntl = self._orig_fcntl
        cli.LOCK_RETRY_DELAY_SECONDS = self._orig_delay
        cli.LOCK_RETRY_ATTEMPTS = self._orig_attempts
        self.tmp.cleanup()

    def test_fallback_lock_excludes_concurrent_acquire_then_releases(self):
        first = cli.acquire_lock()
        self.assertIsNotNone(first, "fcntl が無くてもロックを取得できるべき")

        second = cli.acquire_lock()
        self.assertIsNone(second, "先に取得済みの場合は相互排他されるべき")

        first.close()

        third = cli.acquire_lock()
        self.assertIsNotNone(third, "close() 後は再取得できるべき")
        third.close()


class LockErrorMessageTest(unittest.TestCase):
    """I: ファイルシステムエラーとロック競合をログ上で区別する。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._orig_lock = cli.LOCK_PATH
        self._orig_delay = cli.LOCK_RETRY_DELAY_SECONDS
        self._orig_attempts = cli.LOCK_RETRY_ATTEMPTS
        cli.LOCK_RETRY_DELAY_SECONDS = 0.01
        cli.LOCK_RETRY_ATTEMPTS = 2

    def tearDown(self):
        cli.LOCK_PATH = self._orig_lock
        cli.LOCK_RETRY_DELAY_SECONDS = self._orig_delay
        cli.LOCK_RETRY_ATTEMPTS = self._orig_attempts
        self.tmp.cleanup()

    @unittest.skipUnless(cli.fcntl is not None, "fcntl 前提のテスト（POSIX 専用）")
    def test_contention_logs_differently_from_fs_error(self):
        # 競合ケース: 他プロセスがロックを保持している
        cli.LOCK_PATH = os.path.join(self.tmp.name, "cache", "claude_daily_log.lock")
        os.makedirs(os.path.dirname(cli.LOCK_PATH), exist_ok=True)
        holder = open(cli.LOCK_PATH, "w")
        cli.fcntl.flock(holder, cli.fcntl.LOCK_EX | cli.fcntl.LOCK_NB)
        try:
            with self.assertLogs(level="INFO") as captured:
                result = cli.acquire_lock()
        finally:
            cli.fcntl.flock(holder, cli.fcntl.LOCK_UN)
            holder.close()
        self.assertIsNone(result)
        self.assertTrue(any("競合" in message for message in captured.output))
        self.assertFalse(any("ファイルシステムエラー" in message for message in captured.output))

        # ファイルシステムエラーケース: 親ディレクトリの代わりに通常ファイルを置いて makedirs を失敗させる
        blocked_parent = os.path.join(self.tmp.name, "not_a_dir")
        with open(blocked_parent, "w", encoding="utf-8") as handle:
            handle.write("x")
        cli.LOCK_PATH = os.path.join(blocked_parent, "sub", "claude_daily_log.lock")
        with self.assertLogs(level="WARNING") as captured:
            result = cli.acquire_lock()
        self.assertIsNone(result)
        self.assertTrue(any("ファイルシステムエラー" in message for message in captured.output))
        self.assertFalse(any("競合" in message for message in captured.output))


if __name__ == "__main__":
    unittest.main()
