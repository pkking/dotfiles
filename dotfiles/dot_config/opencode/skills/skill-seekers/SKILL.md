---
name: skill-seekers
description: Generate LLM skills from documentation, codebases, and GitHub repositories
---

# Skill Seekers

## Prerequisites

```bash
pip install skill-seekers
# Or: uv pip install skill-seekers
```

## Commands

| Source | Command |
|--------|---------|
| Local code | `skill-seekers-codebase --directory ./path` |
| Docs URL | `skill-seekers scrape --url https://...` |
| GitHub | `skill-seekers github --repo owner/repo` |
| PDF | `skill-seekers pdf --file doc.pdf` |

## Quick Start

```bash
# Analyze local codebase
skill-seekers-codebase --directory /path/to/project --output output/my-skill/

# Package for Claude
yes | skill-seekers package output/my-skill/ --no-open
```

## Options

| Flag | Description |
|------|-------------|
| `--depth surface/deep/full` | Analysis depth |
| `--skip-patterns` | Skip pattern detection |
| `--skip-test-examples` | Skip test extraction |
| `--ai-mode none/api/local` | AI enhancement |

---

# Skill_Seekers Codebase

## Description

Local codebase analysis and documentation generated from code analysis.

**Path:** `/home/lcr/Skill_Seekers`
**Files Analyzed:** 140
**Languages:** Python
**Analysis Depth:** deep

## When to Use This Skill

Use this skill when you need to:
- Understand the codebase architecture and design patterns
- Find implementation examples and usage patterns
- Review API documentation extracted from code
- Check configuration patterns and best practices
- Explore test examples and real-world usage
- Navigate the codebase structure efficiently

## ⚡ Quick Reference

### Codebase Statistics

**Languages:**
- **Python**: 140 files (100.0%)

**Analysis Performed:**
- ✅ API Reference (C2.5)
- ✅ Dependency Graph (C2.6)
- ✅ Design Patterns (C3.1)
- ✅ Test Examples (C3.2)
- ✅ Configuration Patterns (C3.4)
- ✅ Architectural Analysis (C3.7)

### 🎨 Design Patterns Detected

*From C3.1 codebase analysis (confidence > 0.7)*

- **Factory**: 44 instances
- **Strategy**: 28 instances
- **Observer**: 8 instances
- **Builder**: 6 instances
- **Command**: 3 instances

*Total: 90 high-confidence patterns*

*See `references/patterns/` for complete pattern analysis*

## 📝 Code Examples

*High-quality examples extracted from test files (C3.2)*

**Instantiate InsightsStream: Test complete pipeline: GitHub URL → Basic analysis → Merged output

This tests the fast path (1-2 minutes) without C3.x analysis.** (complexity: 1.00)

```python
insights_stream = InsightsStream(metadata={'stars': 1234, 'forks': 56, 'language': 'Python', 'description': 'A test project'}, common_problems=[{'title': 'Installation fails on Windows', 'number': 42, 'state': 'open', 'comments': 15, 'labels': ['bug', 'windows']}, {'title': 'Import error with Python 3.6', 'number': 38, 'state': 'open', 'comments': 10, 'labels': ['bug', 'python']}], known_solutions=[{'title': 'Fixed: Module not found', 'number': 35, 'state': 'closed', 'comments': 8, 'labels': ['bug']}], top_labels=[{'label': 'bug', 'count': 25}, {'label': 'enhancement', 'count': 15}, {'label': 'documentation', 'count': 10}])
```

**Instantiate InsightsStream: Test complete router generation workflow with GitHub streams.

Validates:
1. Router config created
2. Router SKILL.md includes GitHub metadata
3. Router SKILL.md includes README quick start
4. Router SKILL.md includes common issues
5. Routing keywords include GitHub labels (2x weight)** (complexity: 1.00)

```python
insights_stream = InsightsStream(metadata={'stars': 5000, 'forks': 250, 'language': 'Python', 'description': 'Fast test framework'}, common_problems=[{'title': 'OAuth setup fails', 'number': 150, 'state': 'open', 'comments': 30, 'labels': ['bug', 'oauth']}, {'title': 'Async deadlock', 'number': 142, 'state': 'open', 'comments': 25, 'labels': ['async', 'bug']}, {'title': 'Token refresh issue', 'number': 130, 'state': 'open', 'comments': 20, 'labels': ['oauth']}], known_solutions=[{'title': 'Fixed OAuth redirect', 'number': 120, 'state': 'closed', 'comments': 15, 'labels': ['oauth']}, {'title': 'Resolved async race', 'number': 110, 'state': 'closed', 'comments': 12, 'labels': ['async']}], top_labels=[{'label': 'oauth', 'count': 45}, {'label': 'async', 'count': 38}, {'label': 'bug', 'count': 30}])
```

**Instantiate Graph: test k is 3** (complexity: 1.00)

```python
G = nx.Graph([(1, 6), (1, 7), (1, 8), (1, 9), (2, 6), (2, 7), (2, 8), (2, 10), (3, 6), (3, 8), (3, 9), (3, 10), (4, 7), (4, 8), (4, 9), (4, 10), (5, 6), (5, 7), (5, 9), (5, 10)])
```

**Instantiate Graph: test k is 4** (complexity: 1.00)

```python
G = nx.Graph([(8, 1), (8, 2), (8, 3), (8, 4), (8, 5), (9, 1), (9, 2), (9, 3), (9, 4), (9, 7), (10, 1), (10, 2), (10, 3), (10, 4), (10, 6), (11, 1), (11, 2), (11, 5), (11, 6), (11, 7), (12, 1), (12, 3), (12, 5), (12, 6), (12, 7), (13, 2), (13, 4), (13, 5), (13, 6), (13, 7), (14, 3), (14, 4), (14, 5), (14, 6), (14, 7)])
```

**Instantiate Graph: test k is 5** (complexity: 1.00)

```python
G = nx.Graph([(8, 1), (8, 2), (8, 3), (8, 4), (8, 5), (8, 6), (9, 1), (9, 2), (9, 3), (9, 4), (9, 5), (9, 7), (10, 1), (10, 2), (10, 3), (10, 4), (10, 6), (10, 7), (11, 1), (11, 2), (11, 3), (11, 5), (11, 6), (11, 7), (12, 1), (12, 2), (12, 4), (12, 5), (12, 6), (12, 7), (13, 1), (13, 3), (13, 4), (13, 5), (13, 6), (13, 7), (14, 2), (14, 3), (14, 4), (14, 5), (14, 6), (14, 7)])
```

**Instantiate Graph: test k is 6** (complexity: 1.00)

```python
G = nx.Graph([(9, 1), (9, 2), (9, 3), (9, 4), (9, 5), (9, 6), (9, 7), (10, 1), (10, 2), (10, 3), (10, 4), (10, 5), (10, 6), (10, 8), (11, 1), (11, 2), (11, 3), (11, 4), (11, 5), (11, 7), (11, 8), (12, 1), (12, 2), (12, 3), (12, 4), (12, 6), (12, 7), (12, 8), (13, 1), (13, 2), (13, 3), (13, 5), (13, 6), (13, 7), (13, 8), (14, 1), (14, 2), (14, 4), (14, 5), (14, 6), (14, 7), (14, 8), (15, 1), (15, 3), (15, 4), (15, 5), (15, 6), (15, 7), (15, 8), (16, 2), (16, 3), (16, 4), (16, 5), (16, 6), (16, 7), (16, 8)])
```

**test out edges multi** (complexity: 1.00)

```python
G.add_edge(0, 1, 2)
assert sorted(G.out_edges()) == [(0, 1), (0, 1), (0, 2), (1, 0), (1, 2), (2, 0), (2, 1)]
```

**test in edges** (complexity: 1.00)

```python
G.add_edge(0, 1, 2)
assert sorted(G.in_edges()) == [(0, 1), (0, 1), (0, 2), (1, 0), (1, 2), (2, 0), (2, 1)]
```

**test in edges no keys** (complexity: 1.00)

```python
G.add_edge(0, 1, 2)
assert sorted(G.in_edges()) == [(0, 1), (0, 1), (0, 2), (1, 0), (1, 2), (2, 0), (2, 1)]
```

**Instantiate array: Modularity matrix** (complexity: 1.00)

```python
B = np.array([[-1.125, 0.25, 0.25, 0.625, 0.0], [0.25, -0.5, 0.5, -0.25, 0.0], [0.25, 0.5, -0.5, -0.25, 0.0], [0.625, -0.25, -0.25, -0.125, 0.0], [0.0, 0.0, 0.0, 0.0, 0.0]])
```

*See `references/test_examples/` for all extracted examples*

## ⚙️ Configuration Patterns

*From C3.4 configuration analysis*

**Configuration Files Analyzed:** 23
**Total Settings:** 165
**Patterns Detected:** 0

**Configuration Types:**
- unknown: 23 files

*See `references/config_patterns/` for detailed configuration analysis*

## 📚 Available References

This skill includes detailed reference documentation:

- **API Reference**: `references/api_reference/` - Complete API documentation
- **Dependencies**: `references/dependencies/` - Dependency graph and analysis
- **Patterns**: `references/patterns/` - Detected design patterns
- **Examples**: `references/test_examples/` - Usage examples from tests
- **Configuration**: `references/config_patterns/` - Configuration patterns

---

**Generated by Skill Seeker** | Codebase Analyzer with C3.x Analysis
