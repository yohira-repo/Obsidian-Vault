"""同一ディレクトリへの一時ファイル書き込み + os.replace() によるアトミックな書き込み。

セッション終了時に呼ばれるフックが途中で kill された場合でも、手書きファイルが
空・中途半端な状態にならないようにするためのヘルパー。
"""
import os
import tempfile


def write_text_atomic(path: str, text: str) -> None:
    """path と同じディレクトリに一時ファイルを作り、書き切ってから os.replace() で置き換える。

    書き込み中に失敗した場合は一時ファイルを削除してから例外を再送出する。
    """
    directory = os.path.dirname(path) or "."
    fd, tmp_path = tempfile.mkstemp(prefix=".tmp-", suffix=".swap", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise
