import pytest
from student import Student

@pytest.fixture #Used to initialize a Student object for tests. Lets us import data
def student():
    """Create a student for testing"""
    return Student("Alice", 20)

def test_student_creation(student):
    assert student.name == "Alice"
    assert student.age == 20
    assert student.grades == []

def test_add_grade(student):
    student.add_grade(85)
    assert 85 in student.grades
    assert len(student.grades) == 1

def test_add_invalid_grade(student):
    with pytest.raises(ValueError):
        student.add_grade(101)
    
    with pytest.raises(ValueError):
        student.add_grade(-5)

def test_average_grade(student):
    student.add_grade(80)
    student.add_grade(90)
    student.add_grade(70)
    assert student.average_grade() == 80

def test_average_grade_empty(student):
    assert student.average_grade() == 0

@pytest.mark.parametrize("grades, expected", [
    ([70, 80, 90], True),
    ([50, 55, 60], False),
    ([40, 50, 55], False),
    ([59, 59, 59], False),
])
def test_is_passing(student, grades, expected):
    for grade in grades:
        student.add_grade(grade)
    assert student.is_passing() == expected