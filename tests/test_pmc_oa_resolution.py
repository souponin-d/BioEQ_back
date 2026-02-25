from be_system.agents.pdf_downloader_agent import PdfDownloaderAgent
from be_system.agents.pmc_resolver_agent import PMCResolverAgent


def test_oa_xml_parsing_extracts_pdf_and_xml_links():
    agent = PMCResolverAgent()
    xml = """
    <oa>
      <records>
        <record id='PMC123456' license='CC BY'>
          <link format='pdf' href='ftp://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_pdf/aa/bb/file.pdf' />
          <link format='pmc_bioc_xml' href='https://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_bioc/file.xml' />
        </record>
      </records>
    </oa>
    """.strip()

    parsed = agent._parse_oa_xml(raw_xml=xml, pmcid='PMC123456')
    assert parsed['has_oa'] is True
    assert parsed['pdf'] == 'ftp://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_pdf/aa/bb/file.pdf'
    assert parsed['xml'] == 'https://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_bioc/file.xml'


def test_pdf_downloader_normalizes_ncbi_ftp_to_https():
    agent = PdfDownloaderAgent()
    raw = 'ftp://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_pdf/aa/bb/file.pdf'
    normalized = agent._normalize_download_url(raw)
    assert normalized == 'https://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_pdf/aa/bb/file.pdf'
