def not_test[T](obj: T) -> T:
    obj.__test__ = False  # type: ignore[attr-defined]
    return obj
