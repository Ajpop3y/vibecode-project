"""
Secret detection and management for Vibecode.
Implements a hybrid detection engine:
1. Pattern Matching (High Confidence) - Known API key formats
2. Shannon Entropy (Heuristic) - Custom/unknown secrets

ECR #004: Interactive Quarantine System
"""
import re
import math
from typing import List, Tuple, Dict, Set, Optional

# Patterns are ordered from most specific to more general to avoid false positives.
SECRET_PATTERNS: List[Tuple[str, str]] = [
    # === AI / LLM Providers ===
    (r'sk-proj-[a-zA-Z0-9_-]{80,}', 'OpenAI Project Key'),
    (r'sk-[a-zA-Z0-9]{40,}', 'OpenAI Legacy Key'),
    (r'sk-ant-api\d+-[a-zA-Z0-9_-]{90,}', 'Anthropic API Key'),
    (r'AIza[0-9A-Za-z_-]{35}', 'Google API Key'),
    
    # === Version Control & DevOps ===
    (r'github_pat_[a-zA-Z0-9_]{22,}', 'GitHub Fine-grained PAT'),
    (r'ghp_[a-zA-Z0-9]{36}', 'GitHub Classic PAT'),
    (r'gho_[a-zA-Z0-9]{36}', 'GitHub OAuth Token'),
    (r'ghs_[a-zA-Z0-9]{36}', 'GitHub Server Token'),
    (r'ghr_[a-zA-Z0-9]{36}', 'GitHub Refresh Token'),
    (r'glpat-[a-zA-Z0-9_-]{20,}', 'GitLab Personal Access Token'),
    (r'glsa-[a-zA-Z0-9_-]{20,}', 'GitLab Service Account Token'),
    
    # === Cloud Providers ===
    (r'AKIA[0-9A-Z]{16}', 'AWS Access Key ID'),
    (r'(?:aws_secret_access_key|AWS_SECRET_ACCESS_KEY)\s*[=:]\s*["\']?([a-zA-Z0-9/+=]{40})["\']?', 'AWS Secret Key'),
    (r'ABIA[0-9A-Z]{16}', 'AWS STS Token'),
    (r'ACCA[0-9A-Z]{16}', 'AWS Account Key'),
    (r'(?:^|[^a-zA-Z0-9])dop_v1_[a-f0-9]{64}', 'DigitalOcean Token'),
    (r'(?:^|[^a-zA-Z0-9])do_oauth_[a-f0-9]{64}', 'DigitalOcean OAuth'),
    
    # === Payment Providers ===
    (r'sk_live_[a-zA-Z0-9]{24,}', 'Stripe Live Secret Key'),
    (r'sk_test_[a-zA-Z0-9]{24,}', 'Stripe Test Secret Key'),
    (r'pk_live_[a-zA-Z0-9]{24,}', 'Stripe Live Publishable Key'),
    (r'pk_test_[a-zA-Z0-9]{24,}', 'Stripe Test Publishable Key'),
    (r'rk_live_[a-zA-Z0-9]{24,}', 'Stripe Restricted Key'),
    (r'sq0atp-[a-zA-Z0-9_-]{22,}', 'Square Access Token'),
    (r'sq0csp-[a-zA-Z0-9_-]{43,}', 'Square OAuth Secret'),
    
    # === Communication Platforms ===
    (r'xox[baprs]-[a-zA-Z0-9]{10,}', 'Slack Token'),
    (r'https://hooks\.slack\.com/services/T[a-zA-Z0-9_]{8,}/B[a-zA-Z0-9_]{8,}/[a-zA-Z0-9_]{24,}', 'Slack Webhook URL'),
    (r'[MN][A-Za-z\d]{23,}\.[\w-]{6}\.[\w-]{27,}', 'Discord Bot Token'),
    (r'https://discord(?:app)?\.com/api/webhooks/\d+/[a-zA-Z0-9_-]+', 'Discord Webhook URL'),
    (r'SG\.[a-zA-Z0-9_-]{22}\.[a-zA-Z0-9_-]{43}', 'SendGrid API Key'),
    (r'key-[a-zA-Z0-9]{32}', 'Mailgun API Key'),
    (r'[a-f0-9]{32}-us\d+', 'Mailchimp API Key'),
    
    # === Auth & Identity ===
    (r'ya29\.[0-9A-Za-z_-]+', 'Google OAuth Access Token'),
    (r'EAA[a-zA-Z0-9]{100,}', 'Facebook Access Token'),
    (r'eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*', 'JWT Token'),
    
    # === Databases ===
    (r'(?:mongodb(?:\+srv)?|postgres(?:ql)?|mysql|redis|amqp)://[^:]+:[^@]+@[^\s]+', 'Database Connection String'),
    
    # === Private Keys ===
    (r'-----BEGIN (?:RSA |DSA |EC |OPENSSH |PGP )?PRIVATE KEY(?:\sBLOCK)?-----', 'Private Key Header'),
    (r'-----BEGIN CERTIFICATE-----', 'Certificate Header'),
    
    # === Generic Patterns (more prone to false positives, applied last) ===
    (r'(?:api[_-]?key|apikey|api[_-]?token|access[_-]?token|auth[_-]?token|secret[_-]?key|private[_-]?key|client[_-]?secret)\s*[=:]\s*["\']?([a-zA-Z0-9_-]{20,})["\']?', 'Generic API Key Assignment'),
    (r'(?:password|passwd|pwd)\s*[=:]\s*["\']([^"\']{8,})["\']', 'Password Assignment'),
]

# Compile patterns once for performance
COMPILED_PATTERNS = [(re.compile(pattern, re.IGNORECASE | re.MULTILINE), name) for pattern, name in SECRET_PATTERNS]

# Entropy threshold: 4.5 is typical for base64/random hex
ENTROPY_THRESHOLD = 4.5
MIN_SECRET_LENGTH = 20


class SecretScanner:
    """
    Hybrid detection engine for secrets:
    1. Pattern Matching (High Confidence) - Known API key formats
    2. Shannon Entropy (Heuristic) - Custom/unknown secrets
    
    Maintains state for whitelisting and redaction decisions.
    """
    
    def __init__(self):
        self.whitelist: Set[str] = set()  # Values to ignore
        self.redaction_map: Dict[str, str] = {}  # value -> replacement
    
    @staticmethod
    def calculate_entropy(s: str) -> float:
        """
        Calculates Shannon entropy of a string.
        High entropy (>4.5) suggests random/encrypted data like API keys.
        """
        if not s:
            return 0.0
        prob = [float(s.count(c)) / len(s) for c in dict.fromkeys(list(s))]
        return -sum(p * math.log2(p) for p in prob if p > 0)
    
    def scan_text(self, text: str) -> List[Dict]:
        """
        Scans text for potential secrets using both regex patterns and entropy analysis.
        
        Returns a list of candidates:
        [{'type': str, 'value': str, 'line': int, 'context': str}, ...]
        """
        candidates = []
        lines = text.split('\n')
        seen_values = set()  # Avoid duplicates
        
        for i, line in enumerate(lines):
            # Skip very long lines (likely minified code)
            if len(line) > 1000:
                continue
            
            # 1. Regex Pattern Check (High Confidence)
            for compiled_pattern, name in COMPILED_PATTERNS:
                for match in compiled_pattern.finditer(line):
                    # Get the full match or first capture group
                    val = match.group(1) if match.lastindex else match.group(0)
                    if val and val not in self.whitelist and val not in seen_values:
                        seen_values.add(val)
                        candidates.append({
                            'type': name,
                            'value': val,
                            'line': i + 1,
                            'context': self._truncate_context(line.strip()),
                            'confidence': 'high'
                        })
            
            # 2. Entropy Check (Heuristic) - Only for assignment lines
            if '=' in line or ':' in line:
                # Find potential secret strings (length >= 20)
                words = re.findall(r'[a-zA-Z0-9+/=_-]{20,}', line)
                for word in words:
                    if word in self.whitelist or word in seen_values:
                        continue
                    
                    entropy = self.calculate_entropy(word)
                    if entropy > ENTROPY_THRESHOLD:
                        # Avoid re-flagging regex matches
                        if word not in seen_values:
                            seen_values.add(word)
                            candidates.append({
                                'type': 'High Entropy (Potential Secret)',
                                'value': word,
                                'line': i + 1,
                                'context': self._truncate_context(line.strip()),
                                'confidence': 'medium',
                                'entropy': round(entropy, 2)
                            })
        
        return candidates
    
    def scan_files(self, file_data: List[Tuple[str, str]]) -> List[Dict]:
        """
        Scans multiple files for secrets.
        
        Args:
            file_data: List of (filepath, content) tuples
            
        Returns:
            List of candidate secrets with file paths included
        """
        all_candidates = []
        for filepath, content in file_data:
            candidates = self.scan_text(content)
            for c in candidates:
                c['file'] = filepath
            all_candidates.extend(candidates)
        return all_candidates
    
    def _truncate_context(self, context: str, max_len: int = 100) -> str:
        """Truncates context line for display."""
        if len(context) > max_len:
            return context[:max_len] + '...'
        return context
    
    def add_to_whitelist(self, value: str):
        """Add a value to the ignore list."""
        self.whitelist.add(value)
        if value in self.redaction_map:
            del self.redaction_map[value]
    
    def add_redaction(self, value: str, replacement: str = '[REDACTED SECRET]'):
        """Mark a value for redaction."""
        self.redaction_map[value] = replacement
        if value in self.whitelist:
            self.whitelist.remove(value)
    
    def apply_redactions(self, text: str) -> str:
        """Applies all registered redactions to the text."""
        result = text
        for secret, replacement in self.redaction_map.items():
            result = result.replace(secret, replacement)
        return result
    
    def clear(self):
        """Reset scanner state."""
        self.whitelist.clear()
        self.redaction_map.clear()


# === Legacy API (Deprecated - for backwards compatibility) ===
# These functions are deprecated in favor of SecretScanner class

def scrub_secrets(text: str) -> str:
    """
    DEPRECATED: Use SecretScanner.apply_redactions() instead.
    
    Simple auto-scrub using regex patterns only (no user review).
    Kept for backwards compatibility with existing renderers.
    """
    scrubbed = text
    for compiled_pattern, secret_type in COMPILED_PATTERNS:
        scrubbed = compiled_pattern.sub('***REDACTED_SECRET***', scrubbed)
    return scrubbed
