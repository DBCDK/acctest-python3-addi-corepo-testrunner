#! groovy
@Library('microsearch')_

// This has to be declared outside the pipeline since variables
// declared in 'environment' cannot be used by 'agent'.
// See: https://issues.jenkins-ci.org/browse/JENKINS-43911
def python3ImageVersion = findLastSuccessfulBuildNumber('Docker-base-debian-python3/job/master')

def ownerEmail = "os-team@dbc.dk"
def ownerSlack = "search"

properties([
    disableConcurrentBuilds(),
    pipelineTriggers([
        triggers: [
            [
                $class: 'jenkins.triggers.ReverseBuildTrigger',
                upstreamProjects: "../Docker-base-debian-python3/job/master", threshold: hudson.model.Result.SUCCESS
            ]
        ]
    ])
])

pipeline {
    agent {
        docker {
            label 'devel10'
            image "docker.dbc.dk/dbc-debian-python3:${python3ImageVersion}"
            args '-u 0:0'
        }
    }
    options {
        buildDiscarder(logRotator(artifactDaysToKeepStr: "", artifactNumToKeepStr: "", daysToKeepStr: "30", numToKeepStr: "30"))
        timestamps()
    }
    environment {
        RSYNC_TARGETS = credentials('debian-rsync-python3')
    }
    stages {
        stage("build") {
            steps {
                script {
                    if (! env.BRANCH_NAME) {
                        currentBuild.rawBuild.result = Result.ABORTED
                        throw new hudson.AbortException('Job Started from non MultiBranch Build')
                    } else {
                        println(" Building BRANCH_NAME == ${BRANCH_NAME}")
                    }
                }
                script {
                    sh " rm -rf copyright.txt deb_dist/ dist/ *.tar.gz *.egg-info "
                    sh " python3 setup.py nosetests --with-xunit "
                    sh " python3 setup.py --no-user-cfg --command-packages=stdeb.command sdist_dsc --debian-version=${env.BUILD_NUMBER} --verbose --copyright-file copyright.txt -z stable "
                    sh '''
                        for dir in deb_dist/*/; do
                            (cd $dir && debuild -us -uc -b)
                        done
                     '''
                }
            }
        }
        stage("upload") {
            steps {
                script {
                    if (env.BRANCH_NAME == 'master') {
                        sh '''
                            cd deb_dist
                            rm -f *_source.changes # No 'Binary' field - cannot upload
                            for changes in *.changes; do
                                for rsync in ${RSYNC_TARGETS}; do
                                    rsync -av $changes `sed -e '1,/^Files:/d' -e '/^[A-Z]/,$d' -e 's/.* //' $changes` $rsync
                                done
                            done
                        '''
                    }
                }
            }
        }
    }
    post {
        always {
            junit 'nosetests.xml'
            sh ' chown -R --reference=. . '
        }
        failure {
            script {
                if ("${env.BRANCH_NAME}" == 'master') {
                    emailext(
                            recipientProviders: [developers(), culprits()],
                            to: "${ownerEmail}",
                            subject: "[Jenkins] ${env.JOB_NAME} #${env.BUILD_NUMBER} failed",
                            mimeType: 'text/html; charset=UTF-8',
                            body: "<p>The master build failed. Log attached. </p><p><a href=\"${env.BUILD_URL}\">Build information</a>.</p>",
                            attachLog: true)
                    slackSend(channel: "${ownerSlack}",
                            color: 'warning',
                            message: "${env.JOB_NAME} #${env.BUILD_NUMBER} failed and needs attention: ${env.BUILD_URL}",
                            tokenCredentialId: 'slack-global-integration-token')

                } else {
                    // this is some other branch, only send to developer
                    emailext(
                            recipientProviders: [developers()],
                            subject: "[Jenkins] ${env.BUILD_TAG} failed and needs your attention",
                            mimeType: 'text/html; charset=UTF-8',
                            body: "<p>${env.BUILD_TAG} failed and needs your attention. </p><p><a href=\"${env.BUILD_URL}\">Build information</a>.</p>",
                            attachLog: false)
                }
            }
        }
    }
}

