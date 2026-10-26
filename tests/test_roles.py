"""roles.toml against real titles from the database (2026-10-26)."""

from pathlib import Path

import pytest

from jobradar.roles import RoleRules, fold, load_rules, rules_for

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def rules():
    return load_rules(ROOT / "roles.toml")


@pytest.mark.parametrize("title,category", [
    # software development
    ("Senior Software Engineer, Backend", "software"),
    ("Full Stack Engineer(React and GO)", "software"),
    ("Senior Site Reliability Engineer", "software"),
    ("DevOps Engineer - New Grad 2026", "software"),
    ("Senior Salesforce Developer", "software"),  # "sales" inside Salesforce isn't sales
    ("Senior Developer - GPU Driver", "software"),  # a driver, but not a truck driver
    ("Développeuse, développeur Web", "software"),
    (".NET/C# Engineer, TD Securities", "software"),
    ("Director, Deposits Engineering", "software"),
    ("Staff Product Engineer - Brand", "software"),
    # data engineering & analysis
    ("Senior Data Analyst - Fintech (m/f/d)", "data"),
    ("Principal Data Engineer", "data"),
    ("Senior Analytics Engineer - Finance", "data"),
    ("Senior Business Intelligence and Reporting Analyst", "data"),
    ("Manager, Data Initiatives - Ottawa, ON", "data"),
    ("Senior Database Administrator MSSQL", "data"),
    ("Chef d’équipe des données (Data Team Lead)", "data"),
    ("Manager, Mortgage Pricing Analytics", "data"),  # analytics at a bank is wanted
    ("EPIC Clarity Report Writer Analyst/Team Lead", "data"),
    # AI development & implementation
    ("AI Engineer", "ai"),
    ("Forward Deployed Engineer (FDE) - GenAI / Agentic AI", "ai"),
    ("Member of Technical Staff, Training Performance Engineer", "ai"),
    ("Senior ML Research Engineer, Virtual Cell", "ai"),
    ("Applied Scientist, Pro Growth", "ai"),
    ("Ingénieur IA Appliquée Senior", "ai"),
    ("Chercheur.se en apprentissage automatique sénior", "ai"),
    ("Audio Inference Engineer, Model Efficiency", "ai"),
])
def test_wanted(rules, title, category):
    verdict = rules.judge(title)
    assert category in verdict.categories, verdict.reason
    assert rules.wanted(title)


@pytest.mark.parametrize("title", [
    "Financial Advisor - West Vancouver, BC",
    "Enterprise Account Executive (AI Native & Emerging Tech)",
    "Technical Recruiter (6-month Contract)",
    "Mobile Mortgage Advisor (Hamilton/Burlington/Ancaster, ON) - 100% Commission",
    "Customer Experience Associate - Tigrinya Language Skills an Asset",
    "Canada - Data Center Commissioning Engineer (CxE) - Mechanical - All Levels",
    "Regional Data Center Manager - Western Canada",
    "Data Annotation Specialist, Engineering (civil, mechanical, electrical, chemical)",
    "Senior Gameplay Animator (AI) – [Far Cry]",
    "Senior Editor, AI and Technology, Deloitte Global Insights",
    "AI Revenue Strategist New Business",
    "AI Growth Ops",
    "Forward Deployed AI Accelerator, Sales Development",
    "FPGA Digital Design Engineer",
    "Manufacturing Engineer",
    "Senior Financial Analyst (Hybrid)",
    "Credit Risk Analyst Commercial Underwriter",
    "Product Marketing, Data Products",
    "Mgr. Enterprise Risk Mgmt (AI & Cyber)",  # AI mentioned, no builder role
])
def test_not_wanted(rules, title):
    assert not rules.wanted(title)


@pytest.mark.parametrize("title", [
    "Business Analyst co-op",
    "Senior Business Systems Analyst",
    "ServiceNow Senior Implementation Specialist",
    "Manager, Data Governance and Platform",  # governance without a builder role
    "Senior Director, Global Privacy & Data Protection",
    "Release Train Engineer, Deloitte Global Technology",
    "Network Engineer",
])
def test_adjacent_is_off_by_default(rules, title):
    assert rules.judge(title).categories == ["adjacent"]
    assert not rules.wanted(title)


def test_enabling_adjacent(rules):
    data = {"categories": {"adjacent": {"enabled": True, "include": ["business analyst"]}}}
    assert RoleRules.from_dict(data).wanted("Business Analyst co-op")


def test_strong_role_overrides_soft_words(rules):
    # "governance" alone is adjacent; with an engineering role it is data.
    assert rules.judge("Data Governance Engineer").categories == ["data"]


def test_reasons_explain_what_was_dropped(rules):
    assert rules.judge("Financial Advisor").reason == "excluded: financial advisor"
    assert rules.judge("AI Growth Ops").reason == "mentions AI but names no role"
    assert rules.judge("Head Chef").reason == "no matching role"


def test_fold():
    assert fold("Développeur·euse SRE / DevOps") == " developpeur euse sre devops "
    assert fold(".NET/C#") == " .net c# "


def test_rules_for_missing_file(tmp_path):
    rules_for.cache_clear()
    assert rules_for(str(tmp_path)) is None
