"""NetQuota desktop agent (Windows + Linux).

The agent reads cumulative network counters, enriches them with a monotonic
sequence number, and reports them to the NetQuota server. All quota maths
happens server-side; the agent never computes deltas or quotas itself.
"""

__version__ = "0.1.0"