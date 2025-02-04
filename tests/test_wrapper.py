import os
from pathlib import Path
import textwrap


def test_read_env_name():
    from condax.wrapper import Parser

    script1 = textwrap.dedent(
        """
        #!/usr/bin/env bash

        conda run --prefix "/home/user/envs/baba" "/srv/conda/env/baba/bin/my-keke-exe" "$@"

    """
    )
    if os.name != "nt":
        result1 = Parser.parse(script1)
        assert result1
        assert result1.prefix == Path("/home/user/envs/baba")
        assert result1.exec_path.name == "my-keke-exe"
        assert result1.args == "$@"


def test_read_env_name2():
    from condax.wrapper import Parser

    script1 = textwrap.dedent(
        """
        #!/usr/bin/env bash

        conda run --prefix "C:\\Program Files\\user with spaces\\envs\\baba" "C:\\Conda Env\\baba\\bin\\my-keke-exe" "$@"

    """
    )
    if os.name == "nt":
        result1 = Parser.parse(script1)
        assert result1
        assert result1.prefix == Path("C:\\Program Files\\user with spaces\\envs\\baba")
        assert result1.exec_path.name == "my-keke-exe"
        assert result1.args == "$@"
