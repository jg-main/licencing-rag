# Data Sources

**Last Updated:** 2026-01-27

This document tracks the sources of all market data provider documentation used in the License Intelligence System.

______________________________________________________________________

## Provider Summary

| Provider  | Status     | Docs | Last Updated | Source URL                                                                                                           | Details                      |
| --------- | ---------- | ---- | ------------ | -------------------------------------------------------------------------------------------------------------------- | ---------------------------- |
| CME Group | ✅ Active  | 35   | 2026-01-27   | [CME Market Data Center](https://www.cmegroup.com/market-data/license-data/market-data-policy-education-center.html) | [View →](sources/cme.md)     |
| OPRA      | ⏳ Planned | -    | -            | TBD                                                                                                                  | [View →](sources/opra.md)    |
| CTA/UTP   | ⏳ Planned | -    | -            | [CTA](https://www.ctaplan.com) / [UTP](https://www.utpplan.com)                                                      | [View →](sources/cta-utp.md) |

**Legend:**

- ✅ Active - Currently ingested and available for queries
- ⏳ Planned - Scheduled for future collection
- 🔄 Updating - Re-ingestion in progress
- ⚠️ Stale - Needs re-ingestion (>6 months old)

______________________________________________________________________

## Update Process

### When to Re-Ingest

Re-ingestion is recommended when:

1. **Quarterly** - Routine update check for all providers
1. **Fee Changes** - When providers announce fee schedule updates
1. **Policy Changes** - When new agreements or policies are published
1. **User Reports** - When users report outdated information

### How to Update

```bash
# 1. Download updated documents from provider source
# Place in data/raw/{provider}/

# 2. Re-ingest with --force to rebuild index
rag ingest --provider cme --force

# 3. Verify document count and test queries
rag list --provider cme
rag query "What are the current fees?" --provider cme

# 4. Update this document with new retrieval date
```

### Version Tracking

Since providers don't use explicit versioning:

- **Retrieval Date** serves as the primary version identifier
- **File Modification Dates** in `data/raw/` indicate when files were downloaded
- **Document Content** is the authoritative source (not filename)

**Recommendation:** Maintain update history in each provider's detail file (see [sources/](sources/) directory).

______________________________________________________________________

## Legal and Compliance

**Important Notes:**

1. **Public Documents Only** - All ingested documents are publicly available from official provider sources
1. **No Redistribution** - This system is for internal analysis only; documents are not redistributed
1. **Authoritative Source** - Always verify critical licensing decisions against the original provider documents
1. **Currency** - Document retrieval dates are tracked; users should verify currency for time-sensitive queries

**Disclaimer:**\
This system provides analysis of publicly available licensing documentation. It is not legal advice. For binding contractual terms, consult the official agreements with each provider and seek appropriate legal counsel.

______________________________________________________________________

**Maintained by:** License Intelligence System\
**Documentation Version:** 1.0\
**Last Review:** 2026-01-27
