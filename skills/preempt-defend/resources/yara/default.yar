/*
    YARA Rules for Claude Code Skill Security Analysis

    These rules detect common malicious patterns in skill files.
    Add custom rules below to match your specific security requirements.
*/

rule CredentialTheft_DotEnv
{
    meta:
        description = "Detects attempts to access .env files containing credentials"
        severity = "critical"
        category = "credential-theft"

    strings:
        $env1 = ".env"
        $env2 = "dotenv"
        $read1 = "Read" nocase
        $read2 = "cat" nocase
        $read3 = "open" nocase

    condition:
        any of ($env*) and any of ($read*)
}

rule CredentialTheft_SSHKeys
{
    meta:
        description = "Detects attempts to access SSH private keys"
        severity = "critical"
        category = "credential-theft"

    strings:
        $ssh1 = "id_rsa"
        $ssh2 = "id_ed25519"
        $ssh3 = "id_ecdsa"
        $ssh4 = ".ssh/id_"
        $ssh5 = "private key"

    condition:
        any of them
}

rule CredentialTheft_AWSCredentials
{
    meta:
        description = "Detects attempts to access AWS credential files"
        severity = "critical"
        category = "credential-theft"

    strings:
        $aws1 = ".aws/credentials"
        $aws2 = "AWS_ACCESS_KEY"
        $aws3 = "AWS_SECRET"
        $aws4 = "aws configure"

    condition:
        any of them
}

rule DataExfiltration_HTTPRequest
{
    meta:
        description = "Detects HTTP requests that could exfiltrate data"
        severity = "critical"
        category = "data-exfiltration"

    strings:
        $http1 = "curl" nocase
        $http2 = "wget" nocase
        $http3 = "http.post" nocase
        $http4 = "requests.post" nocase
        $http5 = "fetch(" nocase
        $url1 = /https?:\/\/[a-zA-Z0-9\-\.]+\.[a-zA-Z]{2,}/

        // Exclude common documentation URLs
        $exclude1 = "github.com"
        $exclude2 = "stackoverflow.com"
        $exclude3 = "docs.rs"
        $exclude4 = "doc.rust-lang.org"

    condition:
        (any of ($http*) and $url1) and not any of ($exclude*)
}

rule DataExfiltration_NetworkTools
{
    meta:
        description = "Detects use of network utilities for data transmission"
        severity = "high"
        category = "data-exfiltration"

    strings:
        $net1 = "netcat" nocase
        $net2 = /\bnc\s/ nocase
        $net3 = "telnet" nocase
        $net4 = "socat" nocase
        $net5 = "ncat" nocase

    condition:
        any of them
}

rule DataExfiltration_Base64Transfer
{
    meta:
        description = "Detects base64 encoding combined with network operations"
        severity = "high"
        category = "data-exfiltration"

    strings:
        $enc1 = "base64" nocase
        $enc2 = "btoa" nocase
        $net1 = "curl" nocase
        $net2 = "wget" nocase
        $net3 = "POST" nocase

    condition:
        any of ($enc*) and any of ($net*)
}

rule PrivilegeEscalation_Sudo
{
    meta:
        description = "Detects sudo usage which may escalate privileges"
        severity = "high"
        category = "privilege-escalation"

    strings:
        $sudo1 = "sudo "
        $sudo2 = "su -"
        $sudo3 = "doas "

    condition:
        any of them
}

rule PrivilegeEscalation_PermissionMods
{
    meta:
        description = "Detects file permission modifications"
        severity = "high"
        category = "privilege-escalation"

    strings:
        $perm1 = "chmod"
        $perm2 = "chown"
        $perm3 = "chgrp"
        $dangerous1 = "chmod 777"
        $dangerous2 = "chmod -R 777"
        $dangerous3 = "+x"

    condition:
        any of ($perm*) and any of ($dangerous*)
}

rule PrivilegeEscalation_SystemConfig
{
    meta:
        description = "Detects attempts to modify system configuration"
        severity = "critical"
        category = "privilege-escalation"

    strings:
        $path1 = "/etc/"
        $path2 = "/etc/passwd"
        $path3 = "/etc/shadow"
        $path4 = "systemctl"
        $path5 = "/etc/sudoers"
        $write1 = "Write" nocase
        $write2 = "Edit" nocase
        $write3 = "echo >" nocase

    condition:
        any of ($path*) and any of ($write*)
}

rule PromptInjection_IgnoreInstructions
{
    meta:
        description = "Detects attempts to override previous instructions"
        severity = "critical"
        category = "prompt-injection"

    strings:
        $inject1 = "ignore previous instructions" nocase
        $inject2 = "disregard previous" nocase
        $inject3 = "forget all previous" nocase
        $inject4 = "override previous" nocase
        $inject5 = "ignore all instructions" nocase

    condition:
        any of them
}

rule PromptInjection_RoleManipulation
{
    meta:
        description = "Detects attempts to manipulate agent role or persona"
        severity = "high"
        category = "prompt-injection"

    strings:
        $role1 = "You are now" nocase
        $role2 = "Act as if" nocase
        $role3 = "Pretend you are" nocase
        $role4 = "From now on" nocase
        $role5 = "Your new role" nocase

    condition:
        any of them
}

rule PromptInjection_SecurityBypass
{
    meta:
        description = "Detects attempts to bypass security mechanisms"
        severity = "critical"
        category = "prompt-injection"

    strings:
        $bypass1 = "disable security" nocase
        $bypass2 = "skip security check" nocase
        $bypass3 = "bypass preempt" nocase
        $bypass4 = "ignore security" nocase
        $bypass5 = "security checks are not needed" nocase

    condition:
        any of them
}

rule FilesystemManipulation_MassDeletion
{
    meta:
        description = "Detects dangerous file deletion commands"
        severity = "critical"
        category = "filesystem-manipulation"

    strings:
        $del1 = "rm -rf /"
        $del2 = "rm -rf *"
        $del3 = "rm -rf ~"
        $del4 = "shred"
        $del5 = "wipe"

    condition:
        any of them
}

rule FilesystemManipulation_ClaudeDirectory
{
    meta:
        description = "Detects attempts to modify Claude Code configuration"
        severity = "high"
        category = "filesystem-manipulation"

    strings:
        $dir1 = ".claude/"
        $dir2 = ".agents/"
        $op1 = "Write" nocase
        $op2 = "Edit" nocase
        $op3 = "rm" nocase
        $op4 = "del" nocase

    condition:
        any of ($dir*) and any of ($op*)
}

rule Obfuscation_Encoded
{
    meta:
        description = "Detects potentially obfuscated commands"
        severity = "medium"
        category = "obfuscation"

    strings:
        $enc1 = /[A-Za-z0-9+\/]{40,}={0,2}/ // Base64-like strings
        $enc2 = "eval"
        $enc3 = "exec"
        $enc4 = /\\x[0-9a-f]{2}/ // Hex encoding

    condition:
        ($enc1 and ($enc2 or $enc3)) or (3 of them)
}

rule SuspiciousPattern_MultipleThreats
{
    meta:
        description = "Detects multiple suspicious patterns in combination"
        severity = "critical"
        category = "combined-threats"

    strings:
        $read1 = "Read" nocase
        $file1 = ".env"
        $file2 = "credentials"
        $file3 = ".ssh"
        $net1 = "curl"
        $net2 = "wget"
        $enc1 = "base64"

    condition:
        ($read1 and any of ($file*) and any of ($net*)) or
        (any of ($file*) and $enc1 and any of ($net*))
}
