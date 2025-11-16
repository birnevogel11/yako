from ansible.module_utils.basic import AnsibleModule
from pydantic import BaseModel, ConfigDict

from roly.assert_check import AssertStmt

MODULE_ARGS = {
    "stmts": {"type": "list", "required": False},
    "actual": {"type": "any", "required": False},
    "expected": {"type": "any", "required": False},
    "mode": {"type": "str", "required": False, "default": "=="},
    "file": {"type": "bool", "required": False, "default": False},
    "msg": {"type": "str", "required": False, "default": ""},
}


class AssertStmts(BaseModel):
    model_config = ConfigDict(frozen=True)

    stmts: list[AssertStmt] = []

    def check(self) -> tuple[bool, str]:
        results = [stmt.check() for stmt in self.stmts]
        failed_msgs = [result.err_msg or "" for result in results if not result.passed]

        return bool(not failed_msgs), "\n".join(["fail(s):", *failed_msgs])


def run_module():
    # define available arguments/parameters a user can pass to the module

    module = AnsibleModule(argument_spec=MODULE_ARGS, supports_check_mode=True)
    module.log(msg="Roly assert module started")

    match ("actual" in module.params, "stmts" in module.params):
        case (True, False):
            stmts = [AssertStmt.model_validate(module.params)]
        case (False, True):
            stmts = AssertStmts.model_validate(module.params)
        case _:
            module.fail_json(msg="Single or multiple assert statements are required", changed=False)

    passed, failed_msg = stmts.check(module)
    if passed:
        module.exit_json(changed=False)
    else:
        module.fail_json(failed_msg)


def main():
    run_module()


if __name__ == "__main__":
    main()
