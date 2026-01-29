# CME Group - Data Source Details

**Provider:** CME Group Inc.\
**Status:** ✅ Active\
**Document Count:** 35 files\
**Last Retrieved:** 2026-01-27

[← Back to Data Sources](../data-sources.md)

______________________________________________________________________

## Source Information

**Primary Source:**\
[CME Market Data Policy & Education Center](https://www.cmegroup.com/market-data/license-data/market-data-policy-education-center.html)

**Description:**\
Official CME Group market data licensing documentation including Information License Agreements (ILA), fee schedules, exhibits, and policy guides.

**Contact:**\
[CME Market Data Inquiries](https://www.cmegroup.com/market-data/contact-market-data.html)

______________________________________________________________________

## Document Types

- **Information License Agreements (ILA)** - Master agreements for market data licensing
- **Fee Schedules** - Current pricing for market data products and services
- **Exhibits and Appendices** - Supplementary schedules and definitions
- **Market Data Policy Guides** - Educational materials and policy documentation

______________________________________________________________________

## Directory Structure

```
data/raw/cme/
├── Agreements/          # License agreements and contracts
├── Fees/                # Fee schedules and pricing
└── [other documents]    # Policy guides and general documentation
```

______________________________________________________________________

## Versioning Notes

**Important:** CME does not version their public documentation with explicit version numbers.

- **Identification:** Documents are identified by filename and content
- **Change Tracking:** Updates are tracked by retrieval date
- **File Stability:** When CME updates documents, filenames may remain the same but content changes
- **Recommendation:** Perform periodic re-ingestion to capture updates (quarterly recommended)

______________________________________________________________________

## Data Quality

### Completeness

- ✅ **Core ILA agreements** - All major agreement types included
- ✅ **Current fee schedules** - Active pricing documents included
- ✅ **Major exhibits** - Key appendices and schedules included
- ⚠️ **Historical versions** - May not be available publicly

### Known Gaps

- Older versions of fee schedules (not publicly available on CME website)
- Confidential/subscriber-specific agreements (not public)
- Internal CME policy documents (not publicly accessible)
- Some exhibits referenced in agreements may be subscriber-specific

### Document Formats

- **PDF** - Primary format for most agreements and schedules
- **DOCX** - Some policy guides and supplementary documents
- **Coverage** - Both formats ingested with equal fidelity

______________________________________________________________________

## Update History

### 2026-01-27 - Initial Collection

- **Documents:** 35 files retrieved from Policy & Education Center
- **Scope:** ILA agreements, fee schedules (Agreements/, Fees/ subdirectories), policy guides
- **Method:** Manual download from public CME website
- **Validation:** All files successfully extracted and chunked

### Future Updates

**Next Review:** 2026-04-27 (Quarterly)\
**Trigger Events:**

- CME fee schedule announcements
- New agreement versions published
- User reports of outdated information

______________________________________________________________________

## Re-Ingestion Instructions

```bash
# 1. Download updated documents from CME source
# Visit: https://www.cmegroup.com/market-data/license-data/market-data-policy-education-center.html
# Save to: data/raw/cme/

# 2. Re-ingest with --force to rebuild indexes
rag ingest --source cme --force

# 3. Verify document count
rag list --source cme

# 4. Test with sample queries
rag query "What are the current CME fees?" --source cme
rag query "What is a Subscriber?" --source cme

# 5. Update this file with new retrieval date and notes
```

______________________________________________________________________

## Legal & Compliance Notes

**Public Documents Only:**\
All ingested documents are publicly available from CME's official website. No confidential or subscriber-only materials are included.

**No Redistribution:**\
This system is for internal analysis only. Documents are not redistributed or made available to external parties.

**Authoritative Source:**\
For binding contractual terms, always consult the official agreements with CME Group directly. This system provides analysis assistance but is not a substitute for legal review.

**Disclaimer:**\
This documentation provides analysis of publicly available licensing materials. It is not legal advice. Consult CME Group and appropriate legal counsel for contractual matters.

______________________________________________________________________

**Document Version:** 1.0\
**Last Updated:** 2026-01-27\
**Maintained By:** License Intelligence System
