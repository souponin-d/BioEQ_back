from typing import Any, Literal

from pydantic import BaseModel


class PlannerOutput(BaseModel):
    selected_design: str
    washout_days: int
    requires_rsabe: bool
    estimated_sample_size: int
    notes: str


class ReviewerOutput(BaseModel):
    is_consistent: bool
    comments: str
    risk_flags: list[str]


class PubMedSearchResult(BaseModel):
    query: str
    pmids: list[str]


class PubMedArticle(BaseModel):
    pmid: str
    title: str
    journal: str
    year: str
    abstract: str


class PKParameter(BaseModel):
    value: float
    unit: str
    pmid: str


class PubMedPKAnalysis(BaseModel):
    t_half: list[PKParameter]
    cmax: list[PKParameter]
    notes: str


class FullTextLink(BaseModel):
    pmid: str
    pmcid: str | None
    has_pmc: bool
    pdf_url: str | None
    source: Literal["pmc", "none"]


class DownloadedFile(BaseModel):
    id: str
    url: str
    local_path: str
    sha256: str
    bytes: int


class PdfChunk(BaseModel):
    doc_id: str
    page: int
    chunk_id: str
    text: str


class EvidenceItem(BaseModel):
    param: Literal["t_half", "cmax"]
    value: float
    unit: str | None
    pmid: str
    pmcid: str | None
    source_type: Literal["abstract", "pdf"]
    page: int | None
    quote: str
    confidence: Literal["high", "medium", "low"]


class PKExtractionResult(BaseModel):
    evidence: list[EvidenceItem]
    notes: str


class RetrievalSelection(BaseModel):
    param: Literal["t_half", "cmax"]
    chunks: list[PdfChunk]


class RetrievalResult(BaseModel):
    pmid: str
    pmcid: str | None
    selected_chunks: list[RetrievalSelection]


class OrchestratorResult(BaseModel):
    user_input: dict[str, Any]
    planner_output: PlannerOutput
    pubmed_search: PubMedSearchResult
    pubmed_articles: list[PubMedArticle]
    fulltext_links: list[FullTextLink]
    evidence: list[EvidenceItem]
    reviewer_output: ReviewerOutput
    t_half_values: list[float]
    cmax_values: list[float]
    mean_t_half: float | None
    median_t_half: float | None
    mean_cmax: float | None
    median_cmax: float | None
