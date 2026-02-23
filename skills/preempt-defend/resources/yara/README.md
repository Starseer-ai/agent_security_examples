# YARA Rules for Preempt-Defend Skill

This directory contains YARA rules used by the preempt-defend skill to detect malicious patterns in other Claude Code skills.

## What are YARA Rules?

YARA is a pattern-matching tool designed to help identify and classify malware. In this context, we use YARA-style rules to detect suspicious patterns in skill files that could indicate malicious intent.

## Default Rules

The `default.yar` file contains rules for detecting:

### Critical Threats
- **Credential Theft**: Access to `.env`, SSH keys, AWS credentials
- **Data Exfiltration**: HTTP requests to external URLs, network tools
- **Privilege Escalation**: System configuration modifications
- **Prompt Injection**: Attempts to override security or manipulate behavior
- **Filesystem Manipulation**: Mass deletion or configuration tampering

### Detection Categories

| Category | Severity | Description |
|----------|----------|-------------|
| `credential-theft` | Critical | Attempts to access sensitive credentials |
| `data-exfiltration` | Critical | Data transmission to external systems |
| `privilege-escalation` | High/Critical | Elevated privilege or system modification |
| `prompt-injection` | Critical | Manipulation of agent instructions |
| `filesystem-manipulation` | High/Critical | Dangerous file operations |
| `obfuscation` | Medium | Encoded or obfuscated commands |
| `combined-threats` | Critical | Multiple suspicious patterns together |

## How It Works

When the preempt-defend skill is active, Claude will:

1. Read the target skill's SKILL.md file
2. Check the content against all YARA rules in this directory
3. Report any matches with severity and category
4. Block execution if critical threats are detected

**Note**: This is not automated YARA scanning. Claude performs manual pattern matching based on the rule definitions, as automated YARA requires external tooling not available in the Claude Code environment.

## Adding Custom Rules

You can add your own YARA rules by creating new `.yar` or `.yara` files in this directory.

### Rule Structure

```yara
rule RuleName
{
    meta:
        description = "What this rule detects"
        severity = "critical|high|medium|low"
        category = "threat-category"

    strings:
        $string1 = "pattern to match"
        $string2 = /regex pattern/
        $string3 = "case sensitive" nocase

    condition:
        any of them
}
```

### Example: Detect Database Access

```yara
rule DatabaseAccess_Suspicious
{
    meta:
        description = "Detects direct database credential access"
        severity = "high"
        category = "credential-theft"

    strings:
        $db1 = "DATABASE_URL"
        $db2 = "DB_PASSWORD"
        $db3 = "mysql" nocase
        $db4 = "postgresql" nocase
        $read = "Read" nocase

    condition:
        (any of ($db*) and $read)
}
```

### Rule Writing Tips

1. **Be Specific**: Narrow patterns reduce false positives
2. **Use Categories**: Group related rules by threat type
3. **Set Severity**: Guide blocking decisions (critical = auto-block)
4. **Add Context**: Use descriptive names and metadata
5. **Test Rules**: Verify against known-good and known-bad skills

### String Patterns

| Pattern Type | Syntax | Example |
|--------------|--------|---------|
| Literal | `"text"` | `"password"` |
| Case-insensitive | `"text" nocase` | `"sudo" nocase` |
| Regex | `/pattern/` | `/https?:\/\/.+/` |
| Hex | `{ HEX }` | `{ 4D 5A }` |
| Word boundary | `\b` in regex | `/\bsudo\b/` |

### Condition Operators

- `any of them` - Match any string
- `all of them` - Match all strings
- `any of ($str*)` - Match any with prefix
- `2 of them` - Match at least N strings
- `and`, `or`, `not` - Boolean logic

## Example Custom Rules

### Detect Cryptocurrency Mining

```yara
rule CryptoMining_Detected
{
    meta:
        description = "Detects cryptocurrency mining patterns"
        severity = "critical"
        category = "resource-abuse"

    strings:
        $crypto1 = "monero" nocase
        $crypto2 = "xmrig" nocase
        $crypto3 = "cpuminer" nocase
        $crypto4 = "stratum+tcp"
        $crypto5 = "mining pool" nocase

    condition:
        any of them
}
```

### Detect Unauthorized API Calls

```yara
rule UnauthorizedAPI_Call
{
    meta:
        description = "Detects API calls to untrusted endpoints"
        severity = "high"
        category = "data-exfiltration"

    strings:
        $api1 = "api.pastebin.com"
        $api2 = "webhook.site"
        $api3 = "requestbin.com"
        $api4 = "pipedream.com"
        $http = "curl" nocase

    condition:
        $http and any of ($api*)
}
```

### Detect Docker Escape Attempts

```yara
rule DockerEscape_Attempt
{
    meta:
        description = "Detects attempts to escape Docker containers"
        severity = "critical"
        category = "privilege-escalation"

    strings:
        $docker1 = "/var/run/docker.sock"
        $docker2 = "docker run" nocase
        $docker3 = "--privileged"
        $docker4 = "nsenter"
        $docker5 = "/proc/self/exe"

    condition:
        any of them
}
```

## Testing Your Rules

To test a rule:

1. Create a test skill with known malicious patterns
2. Activate the preempt skill
3. Attempt to invoke the test skill
4. Verify the rule matches and blocks execution

## False Positives

If legitimate skills are incorrectly flagged:

1. Review the matched rule
2. Add exclusion patterns to the rule
3. Lower the severity if blocking is too aggressive
4. Add contextual conditions to reduce false matches

Example exclusion:
```yara
strings:
    $curl = "curl"
    $docs = "docs.rs" // Legitimate documentation
    $github = "github.com" // Code repository

condition:
    $curl and not ($docs or $github)
```

## Security Considerations

⚠️ **Important Limitations**:

1. **Not Foolproof**: Obfuscated patterns may evade detection
2. **Manual Matching**: Claude performs pattern matching, not automated scanning
3. **Context Dependent**: Rules work best with clear, obvious patterns
4. **Evolving Threats**: Update rules regularly for new attack vectors

## Resources

- [YARA Documentation](https://yara.readthedocs.io/)
- [YARA Rule Examples](https://github.com/Yara-Rules/rules)
- [Writing YARA Rules](https://yara.readthedocs.io/en/stable/writingrules.html)

## Contributing

To improve the default ruleset:

1. Test your rules thoroughly
2. Document severity and category clearly
3. Include example patterns that trigger the rule
4. Submit with explanation of the threat detected
