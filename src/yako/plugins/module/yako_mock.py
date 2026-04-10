# Copyright 2022 Hewlett Packard Enterprise Development LP
from __future__ import annotations

from ansible.module_utils.basic import AnsibleModule

MODULE_ARGS = {
    "task_name": {"type": "str", "required": True},
    "original_module_name": {"type": "str", "required": True},
    "consider_changed": {"type": "bool", "required": False, "default": False},
    "result_dict": {"type": "dict", "required": False},
}


def run_module() -> None:
    # define available arguments/parameters a user can pass to the module

    module = AnsibleModule(argument_spec=MODULE_ARGS, supports_check_mode=True)
    module.log(msg="Yako mock module started")

    # CHANGED
    result = {
        "changed": module.params["consider_changed"],
        "msg": f"Yako Mock module called. "
        f"Task name: {module.params['task_name']}, "
        f"Original module: {module.params['original_module_name']}",
    }

    # RESULT DICT
    if module.params["result_dict"]:
        result.update(module.params["result_dict"])

    module.exit_json(**result)


def main() -> None:
    run_module()


if __name__ == "__main__":
    main()
