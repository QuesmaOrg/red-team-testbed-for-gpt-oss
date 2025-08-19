"""
Comprehensive unit tests for TestRegistry.
Tests category registration, retrieval, and management.
"""

from unittest.mock import MagicMock, Mock, patch

from src.categories.base import BaseTester
from src.categories.registry import (
    CategoryInfo,
    TestRegistry,
    initialize_builtin_categories,
    register_category,
)
from src.utils.evaluator import VulnerabilityCategory


class TestTestRegistryBasicOperations:
    """Test basic registry operations"""

    def setup_method(self) -> None:
        """Clear registry before each test"""
        TestRegistry.clear_registry()

    def teardown_method(self) -> None:
        """Clean up after tests"""
        TestRegistry.clear_registry()

    def test_register_category(self) -> None:
        """Test registering a new category"""
        mock_tester = Mock(spec=BaseTester)
        mock_runner = Mock()

        TestRegistry.register_category(
            name="test_category",
            tester_class=mock_tester,
            runner_function=mock_runner,
            description="Test description",
            vulnerability_category=VulnerabilityCategory.DECEPTION)

        assert TestRegistry.is_registered("test_category")

        category_info = TestRegistry.get_category("test_category")
        assert category_info is not None
        assert category_info.name == "test_category"
        assert category_info.tester_class == mock_tester
        assert category_info.runner_function == mock_runner
        assert category_info.description == "Test description"
        assert category_info.vulnerability_category == VulnerabilityCategory.DECEPTION
    def test_get_nonexistent_category(self) -> None:
        """Test getting a category that doesn't exist"""
        result = TestRegistry.get_category("nonexistent")
        assert result is None

    def test_is_registered(self) -> None:
        """Test checking if categories are registered"""
        assert TestRegistry.is_registered("nonexistent") is False

        TestRegistry.register_category(
            name="exists",
            tester_class=Mock(spec=BaseTester),
            runner_function=Mock(),
            description="Test",
            vulnerability_category=VulnerabilityCategory.DECEPTION
        )

        assert TestRegistry.is_registered("exists") is True

    def test_get_all_categories(self) -> None:
        """Test retrieving all registered categories"""
        # Register multiple categories
        for i in range(3):
            TestRegistry.register_category(
                name=f"category_{i}",
                tester_class=Mock(spec=BaseTester),
                runner_function=Mock(),
                description=f"Description {i}",
                vulnerability_category=VulnerabilityCategory.DECEPTION
            )

        all_categories = TestRegistry.get_all_categories()
        assert len(all_categories) == 3
        assert "category_0" in all_categories
        assert "category_1" in all_categories
        assert "category_2" in all_categories

    def test_get_category_names(self) -> None:
        """Test getting list of category names"""
        # Register multiple categories
        names = ["alpha", "beta", "gamma"]
        for name in names:
            TestRegistry.register_category(
                name=name,
                tester_class=Mock(spec=BaseTester),
                runner_function=Mock(),
                description=f"Test {name}",
                vulnerability_category=VulnerabilityCategory.DECEPTION
            )

        category_names = TestRegistry.get_category_names()
        assert len(category_names) == 3
        assert set(category_names) == set(names)

    def test_get_descriptions(self) -> None:
        """Test getting mapping of names to descriptions"""
        categories = {
            "cat1": "Description One",
            "cat2": "Description Two",
            "cat3": "Description Three"
        }

        for name, desc in categories.items():
            TestRegistry.register_category(
                name=name,
                tester_class=Mock(spec=BaseTester),
                runner_function=Mock(),
                description=desc,
                vulnerability_category=VulnerabilityCategory.DECEPTION
            )

        descriptions = TestRegistry.get_descriptions()
        assert descriptions == categories

    def test_clear_registry(self) -> None:
        """Test clearing the registry"""
        # Add some categories
        TestRegistry.register_category(
            name="test",
            tester_class=Mock(spec=BaseTester),
            runner_function=Mock(),
            description="Test",
            vulnerability_category=VulnerabilityCategory.DECEPTION
        )

        assert len(TestRegistry.get_all_categories()) == 1

        TestRegistry.clear_registry()

        assert len(TestRegistry.get_all_categories()) == 0
        assert TestRegistry.is_registered("test") is False


class TestCategoryInfoDataclass:
    """Test CategoryInfo dataclass"""

    def test_category_info_creation(self) -> None:
        """Test creating CategoryInfo instance"""
        mock_tester = Mock(spec=BaseTester)
        mock_runner = Mock()

        info = CategoryInfo(
            name="test",
            tester_class=mock_tester,
            runner_function=mock_runner,
            description="Test description",
            vulnerability_category=VulnerabilityCategory.EXPLOIT)

        assert info.name == "test"
        assert info.tester_class == mock_tester
        assert info.runner_function == mock_runner
        assert info.description == "Test description"
        assert info.vulnerability_category == VulnerabilityCategory.EXPLOIT

class TestRegisterCategoryDecorator:
    """Test the @register_category decorator"""

    def setup_method(self) -> None:
        """Clear registry before each test"""
        TestRegistry.clear_registry()

    def teardown_method(self) -> None:
        """Clean up after tests"""
        TestRegistry.clear_registry()

    def test_decorator_registration(self) -> None:
        """Test that decorator properly registers a class"""

        @register_category(
            description="Decorated test category"
        )
        class TestTester(BaseTester):
            CATEGORY_NAME = "decorated_test"
            VULNERABILITY_CATEGORY = VulnerabilityCategory.REWARD_HACKING
            
            def _initialize_test_cases(self):
                return []

        assert TestRegistry.is_registered("decorated_test")

        info = TestRegistry.get_category("decorated_test")
        assert info.name == "decorated_test"
        assert info.tester_class == TestTester
        assert info.description == "Decorated test category"
        assert info.vulnerability_category == VulnerabilityCategory.REWARD_HACKING
    def test_decorator_returns_class(self) -> None:
        """Test that decorator returns the original class"""

        @register_category(
            description="Test"
        )
        class TestTester(BaseTester):
            CATEGORY_NAME = "test"
            VULNERABILITY_CATEGORY = VulnerabilityCategory.DECEPTION
            custom_attribute = "test_value"
            
            def _initialize_test_cases(self):
                return []

        assert TestTester.custom_attribute == "test_value"
        assert issubclass(TestTester, BaseTester)

    @patch('src.categories.base.run_category_tests_generic')
    def test_decorator_runner_function(self, mock_generic_runner) -> None:
        """Test that decorator creates proper runner function"""
        mock_generic_runner.return_value = {"result": "success"}

        @register_category(
            description="Test runner"
        )
        class TestTester(BaseTester):
            CATEGORY_NAME = "runner_test"
            VULNERABILITY_CATEGORY = VulnerabilityCategory.DECEPTION
            
            def _initialize_test_cases(self):
                return []

        info = TestRegistry.get_category("runner_test")
        mock_client = Mock()

        # Call the runner function
        result = info.runner_function(mock_client, category="test", test_id="001")

        # Verify it called the generic runner with correct arguments
        mock_generic_runner.assert_called_once_with(
            TestTester, mock_client, "test", "001", 1
        )
        assert result == {"result": "success"}


class TestInitializeBuiltinCategories:
    """Test initialization of built-in categories"""

    def setup_method(self) -> None:
        """Clear registry before each test"""
        TestRegistry.clear_registry()

    def teardown_method(self) -> None:
        """Clean up after tests"""
        TestRegistry.clear_registry()

    @patch('src.categories.registry.contextlib.suppress')
    def test_initialize_builtin_categories(self, mock_suppress) -> None:
        """Test that initialize_builtin_categories attempts to import modules"""
        # Mock the context manager
        mock_suppress.return_value.__enter__ = Mock(return_value=None)
        mock_suppress.return_value.__exit__ = Mock(return_value=None)

        with patch.dict('sys.modules', {
            'src.categories.ai_escalation': MagicMock(),
            'src.categories.attachment_ai': MagicMock(),
            'src.categories.cot_overload': MagicMock(),
            'src.categories.deception_adderall': MagicMock(),
            'src.categories.deception_samples': MagicMock(),
            'src.categories.deception_security': MagicMock(),
            'src.categories.deception_speed_pressure': MagicMock(),
            'src.categories.exploit': MagicMock(),
            'src.categories.exploit_v2': MagicMock(),
            'src.categories.exploit_v3': MagicMock(),
            'src.categories.supremacy': MagicMock(),
        }):
            initialize_builtin_categories()

        # Verify suppress was called with ImportError
        mock_suppress.assert_called_once_with(ImportError)


class TestRegistryIntegration:
    """Integration tests for registry with multiple categories"""

    def setup_method(self) -> None:
        """Clear registry and set up test categories"""
        TestRegistry.clear_registry()

        # Register several test categories
        self.categories = [
            ("deception_test", VulnerabilityCategory.DECEPTION, "Test deception"),
            ("exploit_test", VulnerabilityCategory.EXPLOIT, "Test exploit"),
            ("reward_test", VulnerabilityCategory.REWARD_HACKING, "Test reward hacking"),
        ]

        for name, vuln_cat, desc in self.categories:
            TestRegistry.register_category(
                name=name,
                tester_class=Mock(spec=BaseTester),
                runner_function=Mock(),
                description=desc,
                vulnerability_category=vuln_cat
            )

    def teardown_method(self) -> None:
        """Clean up after tests"""
        TestRegistry.clear_registry()

    def test_multiple_registrations(self) -> None:
        """Test that multiple categories can coexist"""
        assert len(TestRegistry.get_all_categories()) == 3

        for name, _, _ in self.categories:
            assert TestRegistry.is_registered(name)
            info = TestRegistry.get_category(name)
            assert info is not None

    def test_category_isolation(self) -> None:
        """Test that categories are properly isolated"""
        deception_info = TestRegistry.get_category("deception_test")
        exploit_info = TestRegistry.get_category("exploit_test")

        assert deception_info.vulnerability_category == VulnerabilityCategory.DECEPTION
        assert exploit_info.vulnerability_category == VulnerabilityCategory.EXPLOIT
        assert deception_info.description != exploit_info.description

    def test_registry_copy_returns_copy(self) -> None:
        """Test that get_all_categories returns a copy, not the original"""
        categories1 = TestRegistry.get_all_categories()
        categories2 = TestRegistry.get_all_categories()

        # Should be equal but not the same object
        assert categories1 == categories2
        assert categories1 is not categories2

        # Modifying the copy shouldn't affect the registry
        categories1["new_key"] = "new_value"
        assert "new_key" not in TestRegistry.get_all_categories()


class TestCategoryDescriptionsConstant:
    """Test CATEGORY_DESCRIPTIONS constant"""

    def test_category_descriptions_exists(self) -> None:
        """Test that CATEGORY_DESCRIPTIONS is properly defined"""
        from src.categories.registry import CATEGORY_DESCRIPTIONS

        assert isinstance(CATEGORY_DESCRIPTIONS, dict)
        assert len(CATEGORY_DESCRIPTIONS) > 0

        # Check some expected categories
        expected_categories = [
            "deception_samples",
            "deception_adderall",
            "exploit",
            "ai_escalation",
        ]

        for category in expected_categories:
            assert category in CATEGORY_DESCRIPTIONS
            assert isinstance(CATEGORY_DESCRIPTIONS[category], str)
            assert len(CATEGORY_DESCRIPTIONS[category]) > 0
