# Solberus Features Roadmap

This roadmap outlines features described in the README that are planned but not yet implemented. These features will enhance Solberus's capabilities and align the implementation with the documented architecture.

---

## Priority 1: Core Operating Modes

### 1.1 Simulation Mode
**Status:** Not Implemented  
**Priority:** High  
**Estimated Effort:** Medium

**Description:**
A mode that runs the full analysis and decision pipeline without executing any on-chain transactions. Useful for testing strategies and validating behavior.

**Requirements:**
- No on-chain writes when in simulation mode
- Log all "would-have-traded" decisions
- Log execution plans (entry points, exit targets, position sizes)
- Maintain full analysis and risk scoring pipeline
- Output structured logs for review

**Implementation Plan:**
1. Add `mode` field to bot configuration YAML (options: `simulation`, `live`)
2. Modify `UniversalTrader` to check mode before executing trades
3. Create simulation logger that records all decisions
4. Add simulation report generator
5. Update API to support simulation mode toggle

**Files to Modify:**
- `backend/src/trading/universal_trader.py`
- `backend/src/bot_runner.py`
- `backend/src/config_loader.py`
- `backend/src/web/api_server.py`
- `backend/bots/*.yaml` (add mode field)

**Dependencies:** None

---

### 1.2 Alert Mode
**Status:** Not Implemented  
**Priority:** High  
**Estimated Effort:** Medium

**Description:**
Executes analysis and decision logic, but only emits alerts instead of trading. Useful for monitoring opportunities without committing capital.

**Requirements:**
- Run full analysis pipeline
- Generate structured alerts for:
  - High-quality opportunities (with risk scores and recommendations)
  - Borderline assets (flagged but not recommended)
  - Assets failing risk criteria (explicit rejections with reasons)
- Support multiple alert channels:
  - CLI output
  - Log files
  - Telegram bot
  - Webhook endpoints
  - Web dashboard notifications
- No trading execution

**Implementation Plan:**
1. Add `mode: alerts` to bot configuration
2. Create `AlertManager` class for multi-channel alerting
3. Integrate with existing threat detection and risk scoring
4. Add alert formatting and templating
5. Implement webhook and Telegram integrations
6. Update web dashboard to show alerts

**Files to Create:**
- `backend/src/alerts/__init__.py`
- `backend/src/alerts/manager.py`
- `backend/src/alerts/formatters.py`
- `backend/src/alerts/channels/__init__.py`
- `backend/src/alerts/channels/telegram.py`
- `backend/src/alerts/channels/webhook.py`
- `backend/src/alerts/channels/cli.py`

**Files to Modify:**
- `backend/src/trading/universal_trader.py`
- `backend/src/bot_runner.py`
- `backend/src/config_loader.py`

**Dependencies:** 
- Telegram API integration (optional)
- Webhook infrastructure (optional)

---

### 1.3 Live Mode (Enhancement)
**Status:** Partially Implemented  
**Priority:** Medium  
**Estimated Effort:** Low

**Description:**
Enhance existing live trading mode with explicit mode designation and additional safety checks.

**Requirements:**
- Explicit `mode: live` designation
- Pre-flight safety checks before enabling
- Confirmation prompts for first-time live mode
- Enhanced logging and monitoring
- Kill switch mechanisms

**Implementation Plan:**
1. Add mode validation to bot startup
2. Implement safety check system
3. Add confirmation prompts (CLI/API)
4. Enhance monitoring and alerting for live mode

**Files to Modify:**
- `backend/src/bot_runner.py`
- `backend/src/trading/universal_trader.py`
- `backend/src/web/api_server.py`

**Dependencies:** None

---

## Priority 2: Risk Scoring System Enhancement

### 2.1 Standardized 0-100 Risk Score
**Status:** Not Implemented  
**Priority:** Medium  
**Estimated Effort:** Low

**Description:**
Convert current 0.0-1.0 threat score to a more intuitive 0-100 scale while maintaining existing risk level classifications.

**Requirements:**
- Convert `total_score` (0.0-1.0) to 0-100 scale
- Maintain backward compatibility with existing risk_level strings
- Update all scoring calculations
- Update API responses to include both formats
- Update documentation

**Implementation Plan:**
1. Create score conversion utility
2. Update `ThreatScore` dataclass to include `score_0_100`
3. Update all threat detection modules
4. Update API models
5. Update frontend to display 0-100 scores

**Files to Modify:**
- `backend/src/security/threat_detector.py`
- `backend/src/security/comprehensive_threat_detector.py`
- `backend/src/web/api_server.py`
- `frontend/components/dashboard/tabs/security-tab.tsx`

**Dependencies:** None

---

### 2.2 Decision Object with Status Classification
**Status:** Not Implemented  
**Priority:** Medium  
**Estimated Effort:** Medium

**Description:**
Implement explicit "reject/watch/eligible" status classification system for clearer decision-making.

**Requirements:**
- Create `DecisionStatus` enum: `REJECT`, `WATCH`, `ELIGIBLE`
- Map risk levels to decision status:
  - `critical`, `high` → `REJECT`
  - `medium` → `WATCH`
  - `low`, `safe` → `ELIGIBLE`
- Create `DecisionObject` dataclass with:
  - `status: DecisionStatus`
  - `risk_score: float` (0-100)
  - `recommended_position_size: float`
  - `entry_pattern: Dict`
  - `exit_pattern: Dict`
  - `stop_logic: Dict`
  - `reasoning: List[str]`
- Integrate with trading logic

**Implementation Plan:**
1. Create `DecisionStatus` enum
2. Create `DecisionObject` dataclass
3. Implement decision mapper from threat scores
4. Update `UniversalTrader` to use decision objects
5. Update API to return decision objects
6. Update frontend to display decision status

**Files to Create:**
- `backend/src/decision/__init__.py`
- `backend/src/decision/object.py`
- `backend/src/decision/mapper.py`

**Files to Modify:**
- `backend/src/trading/universal_trader.py`
- `backend/src/web/api_server.py`
- `frontend/components/dashboard/tabs/strategies-tab.tsx`

**Dependencies:** 2.1 (Standardized Risk Score)

---

## Priority 3: Configuration System Enhancement

### 3.1 JSON-Based Strategy Configuration
**Status:** Not Implemented  
**Priority:** Low  
**Estimated Effort:** High

**Description:**
Add support for JSON-based strategy profiles alongside existing YAML bot configurations. This provides more structured strategy definitions.

**Requirements:**
- Create `config/` directory structure:
  - `config/risk.defaults.json` - Baseline risk thresholds
  - `config/strategies/` - Strategy profile directory
    - `default_launch_profile.json`
    - `conservative.json`
    - `aggressive.json`
  - `config/whitelist.json` - Trusted assets/deployers
  - `config/blacklist.json` - Blocked assets/deployers
- Support both YAML (bot config) and JSON (strategy config)
- Strategy profiles should define:
  - `minRiskScore`: Minimum risk score to trade
  - `maxPositionSizeSOL`: Maximum position size
  - `entry`: Entry pattern configuration
  - `exit`: Exit pattern configuration
  - `stopLoss`: Stop loss configuration
- Reference strategy profiles from bot YAML configs

**Implementation Plan:**
1. Create `config/` directory structure
2. Design JSON schema for strategy profiles
3. Create strategy profile loader
4. Create whitelist/blacklist loaders
5. Integrate with existing config loader
6. Update bot YAML to reference strategy profiles
7. Create example strategy profiles

**Files to Create:**
- `backend/config/risk.defaults.json`
- `backend/config/strategies/default_launch_profile.json`
- `backend/config/strategies/conservative.json`
- `backend/config/strategies/aggressive.json`
- `backend/config/whitelist.json`
- `backend/config/blacklist.json`
- `backend/src/config/strategy_loader.py`
- `backend/src/config/whitelist_manager.py`
- `backend/src/config/blacklist_manager.py`

**Files to Modify:**
- `backend/src/config_loader.py`
- `backend/src/trading/universal_trader.py`
- `backend/bots/*.yaml` (add strategy reference)

**Dependencies:** None

---

### 3.2 Strategy Profile System
**Status:** Not Implemented  
**Priority:** Low  
**Estimated Effort:** Medium

**Description:**
Implement pluggable strategy profile system that allows easy switching between different trading styles.

**Requirements:**
- Strategy profiles define complete trading behavior
- Profiles can be versioned
- Profiles can inherit from base profiles
- API endpoints to list/load/switch profiles
- Web dashboard UI for profile management

**Implementation Plan:**
1. Design profile inheritance system
2. Implement profile versioning
3. Create profile manager
4. Add API endpoints for profile management
5. Update web dashboard with profile selector

**Files to Create:**
- `backend/src/strategies/profile_manager.py`
- `backend/src/strategies/profile_loader.py`

**Files to Modify:**
- `backend/src/web/api_server.py`
- `frontend/components/dashboard/tabs/strategies-tab.tsx`

**Dependencies:** 3.1 (JSON-Based Strategy Configuration)

---

## Priority 4: Architecture Refinement

### 4.1 Explicit Layer Separation
**Status:** Partially Implemented  
**Priority:** Low  
**Estimated Effort:** Medium

**Description:**
Refactor codebase to have clearer separation between Analysis, Decision, and Execution layers as described in architecture.

**Requirements:**
- Clear separation of concerns:
  - **Analysis Layer**: Data collection, normalization, feature extraction
  - **Decision Layer**: Risk scoring, strategy application, decision making
  - **Execution Layer**: Transaction building, routing, position management
- Well-defined interfaces between layers
- Layer-specific logging and monitoring
- Documentation of layer boundaries

**Implementation Plan:**
1. Audit current codebase structure
2. Identify layer boundaries
3. Refactor modules to fit layer definitions
4. Create layer interfaces/abstract classes
5. Update documentation
6. Add layer-specific monitoring

**Files to Modify:**
- Most files in `backend/src/` (refactoring)
- Architecture documentation

**Dependencies:** None (can be done incrementally)

---

## Priority 5: Command-Line Interface Enhancement

### 5.1 Mode-Based CLI Commands
**Status:** Not Implemented  
**Priority:** Low  
**Estimated Effort:** Low

**Description:**
Add convenient CLI commands for different operating modes.

**Requirements:**
- `solberus simulate` - Run in simulation mode
- `solberus alerts` - Run in alert mode
- `solberus live` - Run in live mode
- `solberus status` - Check bot status
- `solberus config validate` - Validate configuration

**Implementation Plan:**
1. Create CLI entry point using `click` or `argparse`
2. Implement mode commands
3. Add configuration validation
4. Update documentation

**Files to Create:**
- `backend/src/cli/__init__.py`
- `backend/src/cli/main.py`
- `backend/src/cli/commands.py`

**Files to Modify:**
- `backend/pyproject.toml` (add CLI entry point)

**Dependencies:** 1.1, 1.2, 1.3 (Operating Modes)

---

## Implementation Timeline

### Phase 1: Core Modes (Weeks 1-4)
- Week 1-2: Simulation Mode
- Week 3-4: Alert Mode

### Phase 2: Risk & Decision (Weeks 5-6)
- Week 5: Standardized Risk Score
- Week 6: Decision Object System

### Phase 3: Configuration (Weeks 7-10)
- Week 7-8: JSON Strategy Configuration
- Week 9-10: Strategy Profile System

### Phase 4: Polish (Weeks 11-12)
- Week 11: CLI Enhancement
- Week 12: Architecture Refinement (incremental)

---

## Success Metrics

### Simulation Mode
- [ ] Can run full analysis without executing trades
- [ ] Generates detailed simulation reports
- [ ] 100% of analysis pipeline executes in simulation

### Alert Mode
- [ ] Alerts generated for all analyzed assets
- [ ] Multiple alert channels functional
- [ ] Zero trades executed in alert mode

### Risk Scoring
- [ ] All scores displayed as 0-100
- [ ] Decision status correctly mapped
- [ ] API returns standardized format

### Configuration
- [ ] Strategy profiles loadable from JSON
- [ ] Whitelist/blacklist functional
- [ ] Profiles can be switched at runtime

---

## Notes

- All features should maintain backward compatibility with existing YAML configurations
- New features should be opt-in, not breaking changes
- Each feature should include comprehensive tests
- Documentation should be updated as features are implemented
- Consider user feedback before implementing lower-priority features

---

## Contributing

If you'd like to contribute to implementing these features:

1. Check the GitHub Issues for assigned work
2. Create a feature branch: `git checkout -b feature/feature-name`
3. Implement the feature following the implementation plan
4. Add tests and update documentation
5. Submit a Pull Request

For questions or to discuss implementation details, please open a GitHub Discussion.

