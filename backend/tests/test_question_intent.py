from app.assistant_tools.question_intent import (
    AcademicQuestionIntent,
    classify_academic_question,
    intent_allows_semantic_retrieval,
    is_concept_question,
)


def test_quiz_due_intent() -> None:
    assert (
        classify_academic_question("When is Quiz 3 due?")
        is AcademicQuestionIntent.ASSIGNMENT_DUE
    )


def test_study_materials_avoids_broad_semantic_retrieval() -> None:
    intent = classify_academic_question(
        "Which materials should I study for Quiz 3?",
        assignment_id="2393399",
    )
    assert intent is AcademicQuestionIntent.ASSIGNMENT_STUDY_MATERIALS
    assert not intent_allows_semantic_retrieval(intent)


def test_mixed_due_date_and_study_materials_is_not_deadline_only() -> None:
    intent = classify_academic_question(
        "When is Quiz 3 due, and which professor materials should I study for it?",
    )
    assert intent is AcademicQuestionIntent.ASSIGNMENT_STUDY_MATERIALS
    assert not intent_allows_semantic_retrieval(intent)


def test_concept_question_does_not_become_quiz_lookup() -> None:
    question = (
        "Explain robot path planning step by step, including A* search and obstacle avoidance"
    )
    assert is_concept_question(question)
    assert classify_academic_question(question) is AcademicQuestionIntent.GENERAL_STUDY
    assert (
        classify_academic_question(question, assignment_id="stale-quiz")
        is AcademicQuestionIntent.GENERAL_STUDY
    )


def test_explicit_canvas_record_questions_are_not_concepts() -> None:
    for question in (
        "Explain Quiz 3",
        "When is Quiz 3 due?",
        "What are the requirements for the Robot Planning Quiz?",
        "How do I submit Quiz 3?",
    ):
        assert not is_concept_question(question)


def test_teaching_request_with_incidental_quiz_word_is_concept() -> None:
    question = "Teach me A* search for my robotics quiz"
    assert is_concept_question(question)
    assert classify_academic_question(question) is AcademicQuestionIntent.GENERAL_STUDY


def test_natural_assessment_questions_keep_canvas_routing() -> None:
    for question in (
        "What is Quiz 3 about?",
        "What is Homework 2?",
        "What is the midterm asking me to do?",
        "Explain how Quiz 3 is graded",
        "Explain what Quiz 3 is asking for",
    ):
        assert not is_concept_question(question)
        assert classify_academic_question(question) in {
            AcademicQuestionIntent.ASSIGNMENT_EXPLAIN,
            AcademicQuestionIntent.ASSIGNMENT_POINTS,
        }


def test_real_concepts_remain_general_study_with_stale_assignment() -> None:
    for question in (
        "Explain A* search step by step",
        "Teach me forward kinematics from zero knowledge",
        "Explain Naive Bayes with an example",
    ):
        assert classify_academic_question(
            question, assignment_id="stale-quiz"
        ) is AcademicQuestionIntent.GENERAL_STUDY
