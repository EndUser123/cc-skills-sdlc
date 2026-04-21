"""
Tests for routing module to improve coverage.

Tests cover query analysis, domain detection, template selection,
and error handling paths in routing.py.
"""

import sys
from pathlib import Path

# Add parent directories for package imports
test_dir = Path(__file__).parent
skills_dir = test_dir.parent.parent
sys.path.insert(0, str(skills_dir))

import pytest  # noqa: E402
from routing import (  # noqa: E402
    # Constants
    DOMAIN_KEYWORDS,
    DOMAIN_PRIORITY,
    HIGH_COMPLEXITY_INDICATORS,
    TEMPLATE_METADATA,
    VALID_TEMPLATES,
    VERIFICATION_DOMAINS,
    ConfigResult,
    # Types
    TemplateResult,
    ValidationResult,
    detect_complexity,
    detect_domain_keywords,
    detect_intent_type,
    detect_verification_domain,
    verification_requirements,
    extract_template_override,
    # Functions
    select_template,
    validate_template,
)


class TestExtractTemplateOverride:
    """Tests for extract_template_override function."""

    def test_valid_template_override_returns_template(self):
        """Given valid template in query, return template name."""
        result, chained = extract_template_override("redesign api template=deep")
        assert result == "deep"
        assert chained == []

    def test_all_valid_templates_accepted(self):
        """All templates in VALID_TEMPLATES should be accepted."""
        for template in VALID_TEMPLATES:
            query = f"some query template={template}"
            result, chained = extract_template_override(query)
            assert result == template, f"Template {template} should be accepted"
            assert chained == []

    def test_invalid_template_returns_none(self):
        """Invalid template not in allowlist returns None."""
        result, chained = extract_template_override("query template=malicious")
        assert result is None
        assert chained == []

    def test_no_override_returns_none(self):
        """Query without template override returns None."""
        result, chained = extract_template_override("just a regular query")
        assert result is None
        assert chained == []

    def test_case_sensitive_template_names(self):
        """Template names are case-sensitive."""
        result, chained = extract_template_override("template=DEEP")
        # DEEP is not in VALID_TEMPLATES (which has lowercase "deep")
        assert result is None
        assert chained == []

    def test_override_with_hyphenated_name(self):
        """Hyphenated template names work correctly."""
        result, chained = extract_template_override("template=data-pipeline")
        assert result == "data-pipeline"
        assert chained == []

    def test_template_chaining_two_templates(self):
        """Template chaining with two templates: template=X+Y"""
        result, chained = extract_template_override("design api template=deep+python")
        assert result == "deep"  # First template is primary
        assert chained == ["python"]  # Second template is chained

    def test_template_chaining_three_templates(self):
        """Template chaining with three templates: template=X+Y+Z"""
        result, chained = extract_template_override("design api template=deep+python+cli")
        assert result == "deep"  # First template is primary
        assert chained == ["python", "cli"]  # Additional templates are chained

    def test_template_chaining_invalid_in_chain(self):
        """Template chaining with invalid template in chain returns None."""
        result, chained = extract_template_override("design api template=deep+malicious")
        # All templates must be valid for chain to be accepted
        assert result is None
        assert chained == []

    def test_template_chaining_duplicate_templates(self):
        """Template chaining allows duplicate templates (user's choice)."""
        result, chained = extract_template_override("design api template=deep+python+python")
        assert result == "deep"
        assert chained == ["python", "python"]


class TestDetectDomainKeywords:
    """Tests for detect_domain_keywords function."""

    def test_cli_domain_detected(self):
        """CLI keywords detected correctly."""
        result = detect_domain_keywords("help with command line parsing")
        assert result == "cli"

    def test_python_domain_detected(self):
        """Python keywords detected correctly."""
        result = detect_domain_keywords("asyncio not working")
        assert result == "python"

    def test_data_pipeline_domain_detected(self):
        """Data pipeline keywords detected correctly."""
        result = detect_domain_keywords("build kafka streaming pipeline")
        assert result == "data-pipeline"

    def test_precedent_domain_detected(self):
        """Precedent/ADR keywords detected correctly."""
        result = detect_domain_keywords("create an architecture decision record")
        assert result == "precedent"

    def test_no_keywords_returns_none(self):
        """Query without domain keywords returns None."""
        result = detect_domain_keywords("just some random text")
        assert result is None

    def test_priority_order_cli_over_python(self):
        """CLI has priority over python when both keywords present."""
        result = detect_domain_keywords("python command line tool")
        assert result == "cli"  # CLI checked first

    def test_case_insensitive_matching(self):
        """Domain detection is case-insensitive."""
        result = detect_domain_keywords("PYTHON ASYNC code")
        assert result == "python"

    def test_all_cli_keywords(self):
        """All CLI keywords should trigger detection."""
        cli_keywords = ["cli", "terminal", "shell", "posix", "exit code", "argument parsing"]
        for keyword in cli_keywords:
            query = f"help with {keyword}"
            result = detect_domain_keywords(query)
            assert result == "cli", f"Keyword '{keyword}' should detect CLI domain"

    def test_all_python_keywords(self):
        """Sample of Python keywords should trigger detection."""
        python_keywords = ["asyncio", "django", "decorator", "context manager"]
        for keyword in python_keywords:
            query = f"fix {keyword}"
            result = detect_domain_keywords(query)
            assert result == "python", f"Keyword '{keyword}' should detect Python domain"


class TestDetectComplexity:
    """Tests for detect_complexity function."""

    def test_redesign_indicates_deep(self):
        """'redesign' keyword indicates deep template."""
        result = detect_complexity("redesign the api")
        assert result == "deep"

    def test_architecture_indicates_deep(self):
        """'architecture' keyword indicates deep template."""
        result = detect_complexity("system architecture review")
        assert result == "deep"

    def test_microservices_indicates_deep(self):
        """'microservices' keyword indicates deep template."""
        result = detect_complexity("convert to microservices")
        assert result == "deep"

    def test_rewrite_indicates_deep(self):
        """'rewrite' keyword indicates deep template."""
        result = detect_complexity("rewrite the backend")
        assert result == "deep"

    def test_from_scratch_indicates_deep(self):
        """'from scratch' indicates deep template."""
        result = detect_complexity("build from scratch")
        assert result == "deep"

    def test_no_indicators_defaults_to_fast(self):
        """Query without complexity indicators defaults to fast."""
        result = detect_complexity("simple bug fix")
        assert result == "fast"

    def test_case_insensitive_detection(self):
        """Complexity detection is case-insensitive."""
        result = detect_complexity("REDESIGN system")
        assert result == "deep"

    def test_all_high_complexity_indicators(self):
        """All high complexity indicators should return 'deep'."""
        for indicator in HIGH_COMPLEXITY_INDICATORS:
            query = f"system {indicator}"
            result = detect_complexity(query)
            assert result == "deep", f"Indicator '{indicator}' should return 'deep'"


class TestDetectIntentType:
    """Tests for detect_intent_type function."""

    def test_improve_with_subsystem_returns_improve_system(self):
        """Improve + subsystem keywords returns IMPROVE_SYSTEM."""
        result = detect_intent_type("improve memory system")
        assert result == "IMPROVE_SYSTEM"

    def test_optimize_with_cks_returns_improve_system(self):
        """Optimize + CKS returns IMPROVE_SYSTEM."""
        result = detect_intent_type("optimize cks queries")
        assert result == "IMPROVE_SYSTEM"

    def test_enhance_with_hooks_returns_improve_system(self):
        """Enhance + hooks returns IMPROVE_SYSTEM."""
        result = detect_intent_type("enhance hooks performance")
        assert result == "IMPROVE_SYSTEM"

    def test_improve_without_subsystem_returns_default(self):
        """Improve without subsystem returns DEFAULT."""
        result = detect_intent_type("improve performance")
        assert result == "DEFAULT"

    def test_subsystem_without_improve_returns_default(self):
        """Subsystem without improve returns DEFAULT."""
        result = detect_intent_type("memory system analysis")
        assert result == "DEFAULT"

    def test_no_keywords_returns_default(self):
        """Query without keywords returns DEFAULT."""
        result = detect_intent_type("random query")
        assert result == "DEFAULT"

    def test_case_insensitive_detection(self):
        """Intent detection is case-insensitive."""
        result = detect_intent_type("IMPROVE memory SYSTEM")
        assert result == "IMPROVE_SYSTEM"

    def test_review_with_architecture_returns_architecture_review(self):
        """Review + architecture keywords returns ARCHITECTURE_REVIEW."""
        result = detect_intent_type("review the microservices architecture")
        assert result == "ARCHITECTURE_REVIEW"

    def test_audit_with_design_returns_architecture_review(self):
        """Audit + design keywords returns ARCHITECTURE_REVIEW."""
        result = detect_intent_type("audit this system design")
        assert result == "ARCHITECTURE_REVIEW"

    def test_assess_with_arch_returns_architecture_review(self):
        """Assess + arch keywords returns ARCHITECTURE_REVIEW."""
        result = detect_intent_type("assess the current arch")
        assert result == "ARCHITECTURE_REVIEW"

    def test_evaluate_with_system_returns_architecture_review(self):
        """Evaluate + system keywords returns ARCHITECTURE_REVIEW."""
        result = detect_intent_type("evaluate the payment system")
        assert result == "ARCHITECTURE_REVIEW"

    def test_review_without_architecture_returns_default(self):
        """Review without architecture keywords returns DEFAULT."""
        result = detect_intent_type("review the code quality")
        assert result == "DEFAULT"

    def test_architecture_without_review_returns_default(self):
        """Architecture without review keywords returns DEFAULT."""
        result = detect_intent_type("improve the microservices architecture")
        # Returns DEFAULT because "improve" needs a subsystem keyword for IMPROVE_SYSTEM
        # and "architecture" alone doesn't trigger ARCHITECTURE_REVIEW (needs review keyword)
        assert result == "DEFAULT"

    def test_architecture_review_case_insensitive(self):
        """ARCHITECTURE_REVIEW detection is case-insensitive."""
        result = detect_intent_type("REVIEW the Architecture")
        assert result == "ARCHITECTURE_REVIEW"


class TestSelectTemplate:
    """Tests for select_template function covering all routing paths."""

    def test_template_override_parameter_highest_priority(self):
        """Template override parameter takes highest priority."""
        result = select_template("python cli tool", template_override="precedent")
        assert result["template"] == "precedent"

    def test_invalid_template_override_raises_error(self):
        """Invalid template override raises ValueError."""
        with pytest.raises(ValueError, match="Invalid template override"):
            select_template("query", template_override="invalid")

    def test_template_override_in_query(self):
        """Template override in query string is honored."""
        result = select_template("redesign api template=deep")
        assert result["template"] == "deep"

    def test_invalid_template_in_query_ignored(self):
        """Invalid template in query is ignored (security validation)."""
        # extract_template_override returns None for invalid templates
        # so routing falls through to other detection methods
        result = select_template("query template=malicious")
        # Falls through to complexity detection since invalid template ignored
        assert result["template"] in VALID_TEMPLATES  # Should return a valid template

    def test_default_domain_used_when_no_keywords(self):
        """Default domain is used when no keywords detected."""
        result = select_template("random query", default_domain="python")
        assert result["template"] == "python"

    def test_env_domain_used_when_no_default_domain(self):
        """Environment domain is used when default_domain not provided."""
        result = select_template("random query", env_domain="cli")
        assert result["template"] == "cli"

    def test_default_domain_overrides_env_domain(self):
        """Default domain parameter takes precedence over env_domain."""
        result = select_template("random query", default_domain="python", env_domain="cli")
        assert result["template"] == "python"

    def test_auto_domain_allows_keyword_detection(self):
        """auto domain allows keyword detection to proceed."""
        result = select_template("command line tool", default_domain="auto")
        assert result["template"] == "cli"  # keyword detected, not auto

    def test_auto_domain_falls_through_to_complexity(self):
        """auto domain falls through to complexity detection."""
        result = select_template("simple bug fix", default_domain="auto")
        assert result["template"] == "fast"  # complexity detection

    def test_invalid_domain_raises_error(self):
        """Invalid domain raises ValueError."""
        with pytest.raises(ValueError, match="Invalid domain"):
            select_template("query", default_domain="invalid")

    def test_keyword_detection_overrides_default_domain(self):
        """Explicit keywords override default domain (non-auto)."""
        # Even though default is python, cli keyword should win
        # But actually, looking at the code, detected_domain takes priority ONLY if domain is not set or is auto
        # Let me re-read the logic...
        # Actually line 342-346: detected_domain is returned directly, ignoring default
        result = select_template("command line tool", default_domain="python")
        assert result["template"] == "cli"  # keyword detection wins

    def test_complexity_detection_when_no_domain_or_keywords(self):
        """Complexity detection used when no domain and no keywords."""
        result = select_template("redesign the system")
        assert result["template"] == "deep"  # complexity detection

    def test_complexity_detection_defaults_to_fast(self):
        """Complexity detection defaults to fast when no indicators."""
        result = select_template("simple query")
        assert result["template"] == "fast"

    def test_full_routing_flow_priority_order(self):
        """Test complete priority chain: override > default > keywords > complexity."""
        # Override wins
        assert (
            select_template("python cli", template_override="precedent")["template"] == "precedent"
        )
        # Keywords win over default
        assert select_template("command line", default_domain="python")["template"] == "cli"
        # Default wins when no keywords
        assert select_template("random", default_domain="python")["template"] == "python"
        # Complexity wins when nothing else
        assert select_template("redesign system")["template"] == "deep"


class TestValidateTemplate:
    """Tests for validate_template function."""

    def test_valid_template_returns_true(self):
        """Valid template returns (True, '')."""
        is_valid, error = validate_template("fast")
        assert is_valid is True
        assert error == ""

    def test_invalid_template_returns_false(self):
        """Invalid template returns (False, error_message)."""
        is_valid, error = validate_template("invalid")
        assert is_valid is False
        assert "Invalid template" in error
        assert "invalid" in error

    def test_all_valid_templates_validate(self):
        """All templates in VALID_TEMPLATES should validate."""
        for template in VALID_TEMPLATES:
            is_valid, error = validate_template(template)
            assert is_valid, f"Template {template} should be valid: {error}"

    def test_error_message_includes_valid_templates(self):
        """Error message includes list of valid templates."""
        is_valid, error = validate_template("wrong")
        assert is_valid is False
        for template in ["fast", "deep", "cli", "python"]:
            assert template in error


class TestConstants:
    """Tests for exported constants."""

    def test_domain_keywords_structure(self):
        """DOMAIN_KEYWORDS has correct structure."""
        assert isinstance(DOMAIN_KEYWORDS, dict)
        assert "cli" in DOMAIN_KEYWORDS
        assert "python" in DOMAIN_KEYWORDS
        assert "data-pipeline" in DOMAIN_KEYWORDS
        assert "precedent" in DOMAIN_KEYWORDS

    def test_valid_templates_is_set(self):
        """VALID_TEMPLATES is a set with expected values."""
        assert isinstance(VALID_TEMPLATES, set)
        assert "fast" in VALID_TEMPLATES
        assert "deep" in VALID_TEMPLATES

    def test_template_metadata_structure(self):
        """TEMPLATE_METADATA has correct structure."""
        assert isinstance(TEMPLATE_METADATA, dict)
        for template in VALID_TEMPLATES:
            assert template in TEMPLATE_METADATA
            metadata = TEMPLATE_METADATA[template]
            assert "complexity" in metadata
            assert "domain" in metadata

    def test_domain_priority_order(self):
        """DOMAIN_PRIORITY has expected order."""
        assert isinstance(DOMAIN_PRIORITY, list)
        assert len(DOMAIN_PRIORITY) == 4
        assert DOMAIN_PRIORITY[0] == "cli"  # Highest priority


class TestTypeDefinitions:
    """Tests for TypedDict type definitions."""

    def test_template_result_type(self):
        """TemplateResult TypedDict can be instantiated."""
        result: TemplateResult = {
            "template": "fast",
            "source": "complexity",
            "confidence": "high",
        }
        assert result["template"] == "fast"

    def test_config_result_type(self):
        """ConfigResult TypedDict can be instantiated."""
        result: ConfigResult = {
            "config": {"default_domain": "python"},
            "source": "file",
            "error": None,
        }
        assert result["source"] == "file"

    def test_validation_result_type(self):
        """ValidationResult TypedDict can be instantiated."""
        result: ValidationResult = {
            "is_valid": True,
            "error_message": "",
            "template_path": Path("test.md"),
        }
        assert result["is_valid"] is True


class TestIntegrationSelectTemplateWithConfig:
    """Integration tests for select_template with load_arch_config."""

    def test_select_template_with_config_no_default_domain(self):
        """When load_arch_config returns None, select_template falls through to keyword detection."""
        # Simulate load_arch_config returning None (no config file)
        config = None
        default_domain = config.get("default_domain") if config else None

        # Should fall through to keyword detection
        result = select_template("command line tool", default_domain=default_domain)
        assert result["template"] == "cli"

    def test_select_template_with_config_default_domain(self):
        """When load_arch_config returns a config, select_template uses default_domain."""
        # Simulate load_arch_config returning a config with python domain
        config = {"default_domain": "python"}
        default_domain = config.get("default_domain")

        # Should use default domain since no keywords detected
        result = select_template("random query", default_domain=default_domain)
        assert result["template"] == "python"

    def test_select_template_with_config_auto_domain(self):
        """When config has auto domain, select_template uses keyword detection."""
        # Simulate load_arch_config returning auto domain
        config = {"default_domain": "auto"}
        default_domain = config.get("default_domain")

        # Should detect cli keyword and return cli template
        result = select_template("command line tool", default_domain=default_domain)
        assert result["template"] == "cli"

    def test_select_template_with_config_and_file_validation(self):
        """Integration: config-based selection produces valid template that exists on filesystem."""
        # Test with actual config values
        test_cases = [
            {"default_domain": "python", "query": "random query", "expected": "python"},
            {"default_domain": "cli", "query": "random query", "expected": "cli"},
            {
                "default_domain": "data-pipeline",
                "query": "random query",
                "expected": "data-pipeline",
            },
            {"default_domain": "precedent", "query": "random query", "expected": "precedent"},
        ]

        for case in test_cases:
            config = {"default_domain": case["default_domain"]}
            default_domain = config.get("default_domain")

            # Select template
            template_result = select_template(case["query"], default_domain=default_domain)
            template = template_result["template"]

            # Verify expected template
            assert template == case["expected"], f"Expected {case['expected']}, got {template}"

            # Verify template is valid
            is_valid, error = validate_template(template)
            assert is_valid, f"Template {template} should be valid: {error}"

    def test_select_template_with_config_priority_integration(self):
        """Integration: verify priority chain works with config-loaded values."""
        # Config sets default to python
        config = {"default_domain": "python"}
        default_domain = config.get("default_domain")

        # Keyword detection should override default domain
        result = select_template("command line tool", default_domain=default_domain)
        assert result["template"] == "cli"  # keyword wins over default

        # Without keywords, default domain should be used
        result = select_template("random query", default_domain=default_domain)
        assert result["template"] == "python"  # default wins

        # Template override parameter should win over everything
        result = select_template(
            "random query", template_override="deep", default_domain=default_domain
        )
        assert result["template"] == "deep"  # override wins

    def test_select_template_full_end_to_end_flow(self):
        """End-to-end: from config load to template selection to file validation."""
        # Simulate a real workflow: load config, select template, validate file exists

        # Step 1: Simulate config loading
        config_scenarios = [
            None,  # No config file
            {"default_domain": "python"},
            {"default_domain": "cli"},
            {"default_domain": "auto"},
        ]

        # Step 2: For each config scenario, test various queries
        test_queries = [
            "command line tool",  # cli keyword
            "asyncio code",  # python keyword
            "simple bug fix",  # complexity detection -> fast
            "redesign the system",  # complexity detection -> deep
            "random query",  # uses default or falls through
        ]

        for config in config_scenarios:
            default_domain = config.get("default_domain") if config else None

            for query in test_queries:
                # Select template
                template_result = select_template(query, default_domain=default_domain)
                template = template_result["template"]

                # Verify template is valid
                is_valid, error = validate_template(template)
                assert is_valid, f"Template '{template}' from config={config}, query='{query}' failed validation: {error}"

                # Verify template is in valid templates set
                assert template in VALID_TEMPLATES, f"Template '{template}' not in VALID_TEMPLATES"


class TestDetectVerificationDomain:
    """Tests for detect_verification_domain function."""

    def test_browser_automation_detected(self):
        """Selenium/webdriver/browser queries map to browser_automation."""
        assert detect_verification_domain("selenium webdriver scrape pages") == "browser_automation"
        assert detect_verification_domain("playwright headless chromium") == "browser_automation"
        assert detect_verification_domain("firefox profile xpath click navigate") == "browser_automation"

    def test_performance_detected(self):
        """Bottleneck/latency/rate limit queries map to performance."""
        assert detect_verification_domain("bottleneck latency rate limit sleep") == "performance"
        assert detect_verification_domain("slow throughput timeout concurrency") == "performance"
        assert detect_verification_domain("retry cooldown fallback chain") == "performance"

    def test_api_integration_detected(self):
        """API/endpoint/REST queries map to api_integration."""
        assert detect_verification_domain("rest api endpoint http client") == "api_integration"
        assert detect_verification_domain("graphql webhook oauth authentication") == "api_integration"
        assert detect_verification_domain("sdk client library pagination") == "api_integration"

    def test_general_fallback(self):
        """Generic queries with no domain keywords map to general."""
        assert detect_verification_domain("refactor module structure") == "general"
        assert detect_verification_domain("rename variables") == "general"
        assert detect_verification_domain("") == "general"

    def test_source_snippet_enriches_detection(self):
        """Source code snippet can trigger domain detection even if query alone doesn't."""
        assert detect_verification_domain(
            "optimize this", "from selenium import webdriver"
        ) == "browser_automation"
        assert detect_verification_domain(
            "fix this", "requests.get(endpoint, timeout=30)"
        ) == "api_integration"

    def test_highest_keyword_count_wins(self):
        """Domain with most keyword hits wins when multiple domains match."""
        # "rate limit" appears in both performance and api_integration
        # But adding more performance-specific keywords should tip the balance
        result = detect_verification_domain("rate limit sleep timeout latency bottleneck")
        assert result == "performance"

    def test_case_insensitive(self):
        """Keyword matching is case-insensitive."""
        assert detect_verification_domain("Selenium WebDriver") == "browser_automation"
        assert detect_verification_domain("BOTTLENECK LATENCY") == "performance"
        assert detect_verification_domain("REST API Endpoint") == "api_integration"


class TestVerificationRequirements:
    """Tests for verification_requirements function."""

    def test_returns_list_for_all_domains(self):
        """Each domain returns a non-empty list of requirements."""
        for domain in VERIFICATION_DOMAINS:
            reqs = verification_requirements(domain)
            assert isinstance(reqs, list), f"{domain} requirements should be a list"
            assert len(reqs) > 0, f"{domain} requirements should not be empty"

    def test_browser_automation_requirements(self):
        """browser_automation has framework verification requirements."""
        reqs = verification_requirements("browser_automation")
        assert any("framework" in r.lower() for r in reqs)
        assert any("api" in r.lower() for r in reqs)

    def test_performance_requirements(self):
        """performance has timing and fallback chain requirements."""
        reqs = verification_requirements("performance")
        assert any("timing" in r.lower() or "constant" in r.lower() for r in reqs)
        assert any("fallback" in r.lower() for r in reqs)

    def test_api_integration_requirements(self):
        """api_integration has endpoint verification requirements."""
        reqs = verification_requirements("api_integration")
        assert any("endpoint" in r.lower() for r in reqs)
        assert any("error" in r.lower() for r in reqs)

    def test_general_requirements(self):
        """general has source file reading requirements."""
        reqs = verification_requirements("general")
        assert any("source" in r.lower() for r in reqs)

    def test_unknown_domain_falls_back_to_general(self):
        """Unknown domain falls back to general requirements."""
        general_reqs = verification_requirements("general")
        unknown_reqs = verification_requirements("nonexistent_domain")
        assert unknown_reqs == general_reqs


class TestVerificationDomainsConstant:
    """Tests for VERIFICATION_DOMAINS constant."""

    def test_is_tuple(self):
        """VERIFICATION_DOMAINS is an immutable tuple."""
        assert isinstance(VERIFICATION_DOMAINS, tuple)

    def test_contains_expected_domains(self):
        """Contains the four expected verification domains."""
        assert "browser_automation" in VERIFICATION_DOMAINS
        assert "performance" in VERIFICATION_DOMAINS
        assert "api_integration" in VERIFICATION_DOMAINS
        assert "general" in VERIFICATION_DOMAINS

    def test_has_four_domains(self):
        """Exactly four verification domains defined."""
        assert len(VERIFICATION_DOMAINS) == 4
