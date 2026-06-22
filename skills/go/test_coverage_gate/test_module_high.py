def add(a, b):
    """Add two numbers."""
    return a + b

def subtract(a, b):
    """Subtract two numbers."""
    return a - b

def multiply(a, b):
    """Multiply two numbers."""
    return a * b

def divide(a, b):
    """Divide two numbers."""
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b

def square(x):
    """Square a number."""
    return x * x


if __name__ == "__main__":
    # Smoke tests for coverage
    assert add(1, 2) == 3
    assert subtract(5, 3) == 2
    assert multiply(2, 4) == 8
    assert divide(10, 2) == 5
    assert square(3) == 9
    try:
        divide(1, 0)
        assert False, "Should raise ValueError"
    except ValueError:
        pass
    print("All tests passed")