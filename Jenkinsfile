// Jenkins CI pipeline for the Social Media Sentiment Analysis project.
// Stages: setup -> lint -> tests -> frontend build -> (optional) docker build.
//
// Runs on any Jenkins agent with: python3, node, docker.
// No credentials required — the pipeline only builds and tests.

pipeline {
    agent any

    environment {
        VENV = ".venv-ci"
        // keep pip quiet and cacheable
        PIP_DISABLE_PIP_VERSION_CHECK = "1"
    }

    options {
        timestamps()
        timeout(time: 30, unit: "MINUTES")
        buildDiscarder(logRotator(numToKeepStr: "20"))
    }

    stages {
        stage("Setup Python") {
            steps {
                sh """
                    python3 -m venv ${VENV}
                    ./${VENV}/bin/pip install -q kafka-python-ng vaderSentiment fastapi 'uvicorn[standard]' psycopg2-binary pandas httpx pytest pyarrow transformers torch --index-url https://pypi.org/simple
                """
            }
        }

        stage("Lint") {
            steps {
                sh """
                    ${VENV}/bin/python -m compileall -q spark producer api evaluation
                """
            }
        }

        stage("Unit Tests") {
            steps {
                sh """
                    ${VENV}/bin/python -m pytest tests/ -v
                """
            }
        }

        stage("Frontend Build") {
            steps {
                dir("frontend") {
                    sh """
                        npm install --no-audit --no-fund
                        npm run build
                    """
                }
            }
        }

        stage("Docker Compose Config") {
            steps {
                sh "docker compose config -q && echo 'compose file valid'"
            }
        }
    }

    post {
        always {
            echo "Pipeline finished — status: ${currentBuild.currentResult}"
        }
        success {
            echo "All stages passed."
        }
        failure {
            echo "Check the failed stage log above."
        }
    }
}
