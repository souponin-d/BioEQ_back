from be_system.agents.abstract_evaluator_agent import AbstractEvaluatorAgent
from be_system.schemas import PubMedArticle


def test_candidate_when_has_pmcid_and_pk_signal():
    agent = AbstractEvaluatorAgent()
    article = PubMedArticle(pmid="1", title="t", journal="j", year="2020", abstract="Cmax and t1/2 were reported")
    result = agent.run([article], {"1": "PMC123"})
    assert result[0].candidate_fulltext is True


def test_not_candidate_without_pmcid():
    agent = AbstractEvaluatorAgent()
    article = PubMedArticle(pmid="1", title="t", journal="j", year="2020", abstract="Cmax reported")
    result = agent.run([article], {"1": None})
    assert result[0].candidate_fulltext is False
