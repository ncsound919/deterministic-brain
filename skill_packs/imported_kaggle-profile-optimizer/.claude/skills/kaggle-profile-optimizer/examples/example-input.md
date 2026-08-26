# Example Inputs

Five realistic user-input examples, each showing a typical prompt plus the structured facts a user provides. These mirror what the skill actually receives: partial, sometimes inconsistent, often missing one or two fields. For each, one assumption the skill would make if something is missing is called out explicitly.

Nothing here is guaranteed to produce medals, upvotes, tiers, or ranking. Any figure shown is a value the user provided, not an invented metric.

---

## 1. Beginner profile (new, few notebooks, no medals, goal junior data scientist)

**Prompt (as typed by the user):**

> "Salut, je debute sur Kaggle. J'ai 2 notebooks publics sur le Titanic et un sur le dataset Iris, aucune medaille. Je vise un poste de data scientist junior. Tu peux auditer mon profil et me dire quoi faire en priorite ?"

**Structured facts provided:**

- Profile URL: `kaggle.com/username-not-shared` (user did not paste the link)
- Goal: junior data scientist
- Current level: beginner (Novice tier), account roughly 2 months old
- Best notebooks: "Titanic - my first submission", "Titanic tuning", "Iris EDA"
- Datasets: none published
- Competitions: Titanic (Getting Started), no ranked finish reported
- Medals / tiers / rankings: none
- GitHub: mentioned "j'ai un GitHub mais rien dessus"
- LinkedIn: yes, "profil de base, pas a jour"
- Weekly time available: about 5 hours
- Horizon: not stated

**One assumption the skill would make (missing horizon):**
Since the horizon is not stated, assume a 90-day working horizon and label it as an assumption. Also assume the three Getting-Started notebooks are educational-quality drafts, not portfolio pieces, until the user confirms otherwise.

---

## 2. Intermediate profile (some notebooks and a bronze medal, goal ML engineer)

**Prompt (as typed by the user):**

> "Voici mon profil : kaggle.com/marie-intermediate. J'ai une dizaine de notebooks, un bronze notebook sur un dataset de churn, et j'ai participe a 3 competitions tabulaires. Je veux me positionner comme ML engineer (pas pure data science, plutot pipelines et mise en prod). Analyse et propose une bio + un plan."

**Structured facts provided:**

- Profile URL: `kaggle.com/marie-intermediate`
- Goal: ML engineer, emphasis on pipelines and production-readiness rather than pure analysis
- Current level: intermediate (Contributor moving toward Expert on notebooks)
- Best notebooks: "Customer churn - feature engineering baseline" (bronze), "Gradient boosting hyperparameter sweep", "Cross-validation done right for tabular data"
- Datasets: 1 published dataset (a cleaned churn dataset), modest usage
- Competitions: 3 tabular competitions, best reported public-leaderboard finish "top 25 percent" on one (user-provided figure)
- Medals / tiers / rankings: 1 bronze notebook medal; no competition medal
- GitHub: `github.com/marie-intermediate`, "quelques repos, dont un template MLOps a moitie fini"
- LinkedIn: yes, headline still says "Data analyst"
- Weekly time available: about 6 hours
- Horizon: 90 days

**One assumption the skill would make (missing dataset usage stats):**
Since precise dataset usage numbers are not provided, assume the published dataset is a secondary asset (supporting reproducibility of a notebook) rather than a headline portfolio piece, and mark dataset-quality evidence as partly `donnees insuffisantes` in the scorecard.

---

## 3. Competition-focused profile (several competitions, wants a progression strategy)

**Prompt (as typed by the user):**

> "Je fais surtout des competitions. J'en ai fait 6, j'ai deux top-10 percent en tabulaire et un top-40 percent en NLP. Je stagne autour de Contributor cote competitions et je ne comprends pas comment monter proprement vers Expert. Donne-moi une strategie de progression, pas juste des tips generiques."

**Structured facts provided:**

- Profile URL: not pasted, user says "je te donnerai le lien si besoin"
- Goal: healthy competition progression toward the next tier, no career target stated
- Current level: Contributor on the competitions track
- Best notebooks: mostly private competition notebooks, 2 public "solution writeups"
- Datasets: none
- Competitions: 6 total (4 tabular, 1 NLP, 1 computer vision), best user-provided finishes "top 10 percent x2 tabular", "top 40 percent NLP"
- Medals / tiers / rankings: no competition medal yet; user-reported percentile finishes only
- GitHub: not mentioned
- LinkedIn: not mentioned
- Weekly time available: about 8 hours, "surtout le week-end"
- Horizon: not stated, but implies "sur quelques mois"

**One assumption the skill would make (no career goal given):**
Since no career goal is stated, assume the objective is genuine skill and standing progression on the competitions track (better generalization, teaming, disciplined validation), not portfolio-for-recruiter framing. State that a career goal would change the recommended notebook-vs-competition balance. Emphasize that tier progression depends on many factors and cannot be guaranteed.

---

## 4. Portfolio-focused profile (recruiter-ready narrative plus LinkedIn/GitHub consistency)

**Prompt (as typed by the user):**

> "Mon profil Kaggle, mon GitHub et mon LinkedIn racontent trois histoires differentes. Je veux un truc coherent qu'un recruteur comprend en 30 secondes. Peux-tu aligner tout ca et me proposer un narratif portfolio pret pour recruteur ? Liens : kaggle.com/dev-portfolio, github.com/dev-portfolio, linkedin.com/in/dev-portfolio"

**Structured facts provided:**

- Profile URL: `kaggle.com/dev-portfolio`
- Goal: recruiter-ready portfolio narrative, cross-platform consistency
- Current level: intermediate, "solide mais mal presente"
- Best notebooks: "Time-series demand forecasting - full pipeline", "Explainable model for credit scoring", "EDA template I reuse everywhere"
- Datasets: 1 published, "un dataset de ventes retail que j'utilise dans 2 notebooks"
- Competitions: 2 finished, no medal, "pas mon focus"
- Medals / tiers / rankings: none provided beyond "Expert notebooks bientot je crois" (unconfirmed)
- GitHub: `github.com/dev-portfolio`, "10 repos, README inegaux"
- LinkedIn: `linkedin.com/in/dev-portfolio`, headline "Passionate about data"
- Weekly time available: about 4 hours
- Horizon: 60 days ("j'ai des entretiens qui arrivent")

**One assumption the skill would make (unconfirmed tier claim):**
Since "Expert notebooks bientot je crois" is unconfirmed, do not treat any tier as achieved. Assume current standing is what is verifiable and mark the tier as `donnees insuffisantes`. Prioritize presentation and narrative alignment over new content, given the 60-day interview horizon and the low weekly time budget.

---

## 5. Career-transition profile (coming from another field, limited time, 6-month horizon)

**Prompt (as typed by the user):**

> "Je viens de la finance (7 ans en controle de gestion), je me reconvertis vers la data. J'ai peu de temps, genre 3-4h par semaine, et je veux un plan realiste sur 6 mois pour que mon profil Kaggle serve ma reconversion. Je suis vraiment debutant cote code Python mais tres a l'aise avec Excel, la finance et l'analyse metier."

**Structured facts provided:**

- Profile URL: none yet, "je viens juste de creer le compte"
- Goal: career transition from finance (controle de gestion) into data, using Kaggle as portfolio support
- Current level: beginner on Kaggle and in Python, strong domain background (finance, business analysis, Excel)
- Best notebooks: none yet, "j'ai suivi le Kaggle Learn Python et Pandas"
- Datasets: none
- Competitions: none
- Medals / tiers / rankings: none
- GitHub: "pas encore, je devrais ?"
- LinkedIn: yes, active, headline "Controleur de gestion", strong finance network
- Weekly time available: 3 to 4 hours
- Horizon: 6 months

**One assumption the skill would make (no domain focus chosen yet):**
Since no target data specialty is chosen, assume the strongest bridge is domain-led analytics (finance, pricing, forecasting, business KPIs) where the user's 7 years of experience is a differentiator, and propose that as the default positioning while flagging it as an assumption the user can override. Keep the 6-month plan deliberately light given the 3 to 4 hour weekly budget, with no promise of a tier or a hire.
