// Jenkins CI pipeline for Sentio.
// Stages: setup -> lint -> unit tests -> frontend build -> compose check
//         -> API tests (Postman/Newman) -> UI tests (Selenium)
//
// Runs on the sentio-jenkins image (python3, node, docker CLI, chromium).
// Triggered by a GitHub push webhook (POST /github-webhook/) and, as a
// fallback when GitHub can't reach your laptop, by polling every 5 minutes.
//
// The API and UI test stages run against the Sentio stack that is already
// up on this machine (startup\windows\start.bat). Jenkins joins the stack's
// Docker network and reaches it as http://api:8000 and http://frontend.
// If the stack isn't running, those two stages are skipped (build UNSTABLE).

pipeline {
    agent any

    environment {
        VENV = ".venv-ci"
        STACK_NETWORK = "sentio_default"   // compose project "sentio"
        API_URL = "http://api:8000"
        UI_URL = "http://frontend"
        PIP_DISABLE_PIP_VERSION_CHECK = "1"
        PIP_CACHE_DIR = "/var/jenkins_home/.cache/pip"
        PIP_DEFAULT_TIMEOUT = "60"
    }

    parameters {
        booleanParam(name: "RUN_E2E", defaultValue: true,
                     description: "Run the Postman and Selenium stages against the running Sentio stack")
    }

    triggers {
        githubPush()                 // GitHub webhook -> http://<jenkins>/github-webhook/
        pollSCM("H/5 * * * *")       // fallback when the webhook can't reach this machine
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

                    # CPU-only PyTorch (~200 MB) instead of the default CUDA build (~2.5 GB)
                    ./${VENV}/bin/pip install --retries 10 --timeout 60 --prefer-binary \
                        torch --index-url https://download.pytorch.org/whl/cpu

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
                        'pymongo==4.10.1' \
                        'mongomock==4.3.0' \
                        setuptools \
                        selenium==4.38.0 \
                        --index-url https://pypi.org/simple
                """
            }
        }

        stage("Lint") {
            steps {
                sh """
                    ${VENV}/bin/python -m compileall -q spark producer api evaluation fetcher scripts docker
                """
            }
        }

        stage("Unit Tests") {
            steps {
                sh """
                    ${VENV}/bin/python -m pytest tests/ -v --ignore=tests/e2e --junitxml=reports/unit.xml
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

        stage("Connect to running stack") {
            when { expression { params.RUN_E2E } }
            steps {
                script {
                    // join the stack's network so http://api:8000 and http://frontend resolve
                    def joined = sh(returnStatus: true, script: """
                        docker network inspect ${STACK_NETWORK} >/dev/null 2>&1 || exit 3
                        docker network connect ${STACK_NETWORK} \$(hostname) 2>/dev/null || true
                        for i in \$(seq 1 30); do
                            curl -sf ${API_URL}/health && exit 0
                            sleep 2
                        done
                        exit 4
                    """)
                    env.STACK_UP = (joined == 0) ? "1" : "0"
                    if (joined != 0) {
                        unstable("Sentio stack not running - start it with startup\\windows\\start.bat to run the API/UI tests")
                    }
                }
            }
        }

        stage("API Tests (Postman/Newman)") {
            when { expression { params.RUN_E2E && env.STACK_UP == "1" } }
            steps {
                sh """
                    mkdir -p reports
                    npx --yes newman@6.2.3 run postman/Sentio.postman_collection.json \
                        -e postman/Sentio-local.postman_environment.json \
                        --env-var baseUrl=${API_URL} \
                        --reporters cli,junit --reporter-junit-export reports/newman.xml
                """
            }
        }

        stage("UI Tests (Selenium)") {
            when { expression { params.RUN_E2E && env.STACK_UP == "1" } }
            steps {
                sh """
                    BASE_URL=${UI_URL} CHROME_BIN=/usr/bin/chromium CHROMEDRIVER=/usr/bin/chromedriver \
                    E2E_SCREENSHOTS=reports/screenshots \
                    ${VENV}/bin/python -m pytest tests/e2e -v --junitxml=reports/selenium.xml
                """
            }
        }
    }

    post {
        always {
            junit allowEmptyResults: true, testResults: "reports/*.xml"
            archiveArtifacts allowEmptyArchive: true, artifacts: "reports/**"
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
