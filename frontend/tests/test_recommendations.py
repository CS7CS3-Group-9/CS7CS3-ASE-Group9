# TDD tests for the recommendations route (GET /dashboard/recommendations)
# TODO: Fixture that creates the Flask test client
# TODO: test_recommendations_returns_200 — GET /dashboard/recommendations returns 200
# TODO: test_recommendations_uses_correct_template — renders recommendations.html
# TODO: test_recommendations_data_is_list — assert 'recommendations' passed to
#       template is a list
# TODO: test_recommendation_has_required_fields — mock backend to return a sample
#       recommendation and assert it contains: title, description, priority, data_source
# TODO: test_recommendations_handles_empty_list — backend returns [] and page
#       still renders without error (shows empty state message)
# TODO: test_recommendations_handles_backend_failure — backend API is down,
#       assert route returns 200 with empty recommendations and an error flag