
pipeline {
    agent any

    environment {
        VENV = ".venv-ci"
        PIP_DISABLE_PIP_VERSION_CHECK = "1"
        PIP_CACHE_DIR = "/var/jenkins_home/.cache/pip"
        PIP_DEFAULT_TIMEOUT = "60"
    }

    options {
        timestamps()
        timeout(time: 60, unit: "MINUTES")
        buildDiscarder(logRotator(numToKeepStr: "20"))
    }

    stages {
        stage("Setup Python") {
            steps {
                sh """
                    if [ ! -d "${VENV}" ]; then
                        python3 -m venv ${VENV}
                    fi

                    mkdir -p "${PIP_CACHE_DIR}"

                    ./${VENV}/bin/pip install \
                        --retries 10 \
                        --timeout 60 \
                        --prefer-binary \
                        kafka-python-ng \
                        vaderSentiment \
                        fastapi \
                        'uvicorn[standard]' \
                        psycopg2-binary \
                        pandas \
                        httpx \
                        pytest \
                        pyarrow \
                        transformers \
                        torch \
                        --index-url https://pypi.org/simple
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
            echo "Pipeline finished - status: ${currentBuild.currentResult}"
        }
        success {
            echo "All stages passed."
        }
        failure {
            echo "Check the failed stage log above."
        }
    }
}
