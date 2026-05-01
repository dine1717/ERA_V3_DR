from prefab_ui.app import PrefabApp
from prefab_ui.components import (
    Badge, Card, CardContent, CardHeader, CardTitle,
    Column, H1, H3, Muted, Row, Tab, Tabs, Text,
)
from prefab_ui.components.charts import BarChart, ChartSeries, PieChart

with PrefabApp(css_class="max-w-5xl mx-auto p-6") as app:
    with Card():
        with CardHeader():
            CardTitle("Job Research Dashboard")
        with CardContent():
            with Tabs(value="overview"):
                with Tab("Overview", value="overview"):
                    with Column(gap=4):
                        with Row(gap=6):
                            with Column(gap=1):
                                Muted("Total Jobs")
                                H1("10")
                            with Column(gap=1):
                                Muted("Keywords Found")
                                H1("32")
                        PieChart(data=[{'name': 'linkedin', 'value': 5}, {'name': 'jobicy', 'value': 5}], data_key="value", name_key="name", show_legend=True)
                with Tab("Listings", value="listings"):
                    with Column(gap=3):
                        with Card():
                            with CardContent():
                                with Column(gap=1):
                                    H3("1. Software Engineer, AI/ML")
                                    with Row(gap=2):
                                        Badge("Google", variant="default")
                                        Badge("Bengaluru, Karnataka, India", variant="default")
                        with Card():
                            with CardContent():
                                with Column(gap=1):
                                    H3("2. Data Scientist")
                                    with Row(gap=2):
                                        Badge("Deloitte", variant="default")
                                        Badge("Bengaluru, Karnataka, India", variant="default")
                        with Card():
                            with CardContent():
                                with Column(gap=1):
                                    H3("3. Data Scientist")
                                    with Row(gap=2):
                                        Badge("Ujjivan Small Finance Bank", variant="default")
                                        Badge("Bangalore Urban, Karnataka, India", variant="default")
                        with Card():
                            with CardContent():
                                with Column(gap=1):
                                    H3("4. Software Engineer Agentic AI")
                                    with Row(gap=2):
                                        Badge("hackajob", variant="default")
                                        Badge("Bengaluru, Karnataka, India", variant="default")
                        with Card():
                            with CardContent():
                                with Column(gap=1):
                                    H3("5. AI/Machine Learning Engineer")
                                    with Row(gap=2):
                                        Badge("Apple", variant="default")
                                        Badge("Bengaluru, Karnataka, India", variant="default")
                        with Card():
                            with CardContent():
                                with Column(gap=1):
                                    H3("6. Senior AI Engineer")
                                    with Row(gap=2):
                                        Badge("Revecore", variant="default")
                                        Badge("USA", variant="default")
                        with Card():
                            with CardContent():
                                with Column(gap=1):
                                    H3("7. Team Lead, AI Engineering")
                                    with Row(gap=2):
                                        Badge("Revecore", variant="default")
                                        Badge("USA", variant="default")
                        with Card():
                            with CardContent():
                                with Column(gap=1):
                                    H3("8. Senior Staff Customer Engineer – Automotive AI Engineer")
                                    with Row(gap=2):
                                        Badge("Sonatus", variant="default")
                                        Badge("Germany", variant="default")
                        with Card():
                            with CardContent():
                                with Column(gap=1):
                                    H3("9. Mechanical Engineer & Python Expert – Freelance AI Trainer")
                                    with Row(gap=2):
                                        Badge("Mindrift", variant="default")
                                        Badge("Romania", variant="default")
                        with Card():
                            with CardContent():
                                with Column(gap=1):
                                    H3("10. Python & React Engineer with AI (Remote, Latam)")
                                    with Row(gap=2):
                                        Badge("Kubikware", variant="default")
                                        Badge("LATAM", variant="default")
                with Tab("Keywords", value="keywords"):
                    with Column(gap=4):
                        H3("Skill Frequency")
                        BarChart(data=[{'keyword': 'Deep Learning', 'count': 6}, {'keyword': 'Docker', 'count': 6}, {'keyword': 'LLM', 'count': 4}, {'keyword': 'TensorFlow', 'count': 4}, {'keyword': 'PyTorch', 'count': 4}, {'keyword': 'SQL', 'count': 3}, {'keyword': 'PostgreSQL', 'count': 3}, {'keyword': 'Reinforcement Learning', 'count': 3}, {'keyword': 'Scikit-learn', 'count': 2}, {'keyword': 'NLP', 'count': 2}], series=[ChartSeries(data_key="count", label="Frequency")], x_axis="keyword", show_legend=False)
                with Tab("Interview", value="interview"):
                    with Column(gap=3):
                        with Card():
                            with CardContent():
                                with Column(gap=1):
                                    H3("Software Engineer, AI/ML")
                                    Text("• How do you version control models and datasets?")
                                    Text("• Describe an end-to-end ML pipeline you designed")
                                    Text("• How do you select the right evaluation metric?")
                                    Text("• What is A/B testing for ML models?")
                                    Text("• Explain gradient descent and its variants (SGD, Adam)")
                        with Card():
                            with CardContent():
                                with Column(gap=1):
                                    H3("Data Scientist")
                                    Text("• How do you optimize a slow SQL query?")
                                    Text("• How do you handle data quality issues in a pipeline?")
                                    Text("• Design a data pipeline for processing 10M events per day")
                                    Text("• Explain batch vs stream processing")
                                    Text("• What is the difference between star schema and snowflake schema?")
                        with Card():
                            with CardContent():
                                with Column(gap=1):
                                    H3("Data Scientist")
                                    Text("• What is data partitioning and why is it important?")
                                    Text("• Explain batch vs stream processing")
                                    Text("• How do you optimize a slow SQL query?")
                                    Text("• What is the difference between star schema and snowflake schema?")
                                    Text("• Design a data pipeline for processing 10M events per day")
                        with Card():
                            with CardContent():
                                with Column(gap=1):
                                    H3("Software Engineer Agentic AI")
                                    Text("• How do you handle ethical considerations in AI systems?")
                                    Text("• Describe a production AI system you have built")
                                    Text("• What is explainability in AI and why does it matter?")
                                    Text("• How do you keep up with the rapidly changing AI landscape?")
                        with Card():
                            with CardContent():
                                with Column(gap=1):
                                    H3("AI/Machine Learning Engineer")
                                    Text("• What evaluation metrics do you use and when?")
                                    Text("• How do you handle imbalanced datasets?")
                                    Text("• Walk through your process for taking a model from prototype to production")
                                    Text("• How do you handle model drift in production?")
                                    Text("• Describe a feature engineering pipeline you have built")
                        with Card():
                            with CardContent():
                                with Column(gap=1):
                                    H3("Senior AI Engineer")
                                    Text("• Describe a production AI system you have built")
                                    Text("• How do you handle ethical considerations in AI systems?")
                                    Text("• Explain supervised vs unsupervised vs reinforcement learning")
                                    Text("• How do you keep up with the rapidly changing AI landscape?")
                        with Card():
                            with CardContent():
                                with Column(gap=1):
                                    H3("Team Lead, AI Engineering")
                                    Text("• What is explainability in AI and why does it matter?")
                                    Text("• Explain supervised vs unsupervised vs reinforcement learning")
                                    Text("• How do you handle ethical considerations in AI systems?")
                                    Text("• Describe a production AI system you have built")
                                    Text("• How do you keep up with the rapidly changing AI landscape?")
                        with Card():
                            with CardContent():
                                with Column(gap=1):
                                    H3("Senior Staff Customer Engineer – Automotive AI Engineer")
                                    Text("• Describe a production AI system you have built")
                                    Text("• How do you keep up with the rapidly changing AI landscape?")
                                    Text("• Explain supervised vs unsupervised vs reinforcement learning")
                                    Text("• How do you handle ethical considerations in AI systems?")
                                    Text("• What is explainability in AI and why does it matter?")
                        with Card():
                            with CardContent():
                                with Column(gap=1):
                                    H3("Mechanical Engineer & Python Expert – Freelance AI Trainer")
                                    Text("• How do you write unit tests in Python? What frameworks do you use?")
                                    Text("• How do you handle database migrations in Django/Flask?")
                                    Text("• Describe how you would design a REST API for a large-scale application")
                                    Text("• What is the difference between a list and a tuple? When would you use each?")
                        with Card():
                            with CardContent():
                                with Column(gap=1):
                                    H3("Python & React Engineer with AI (Remote, Latam)")
                                    Text("• Explain the Python GIL and how it affects multi-threading")
                                    Text("• What is the difference between a list and a tuple? When would you use each?")
                                    Text("• How do you write unit tests in Python? What frameworks do you use?")
                                    Text("• What are Python decorators and give a real-world use case")
                                    Text("• Describe how you would design a REST API for a large-scale application")
