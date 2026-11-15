// One-time init for zero-click Jenkins (AUTO mode in run_jenkins.sh):
// creates the admin user (sentio / sentio123) and disables the first-run
// wizard, so opening localhost:8090 goes straight to the dashboard.
import jenkins.model.*
import hudson.security.*

def jenkins = Jenkins.get()

// admin user + full- control ACL (only if not already configured)
if (jenkins.getSecurityRealm() == null ||
    jenkins.getSecurityRealm().class.simpleName == 'HudsonPrivateSecurityRealm' &&
    !jenkins.getSecurityRealm().allowsSignup()) {
  def realm = new HudsonPrivateSecurityRealm(false)
  realm.createAccount("sentio", "sentio123")
  jenkins.setSecurityRealm(realm)
}

def strategy = new FullControlOnceLoggedInAuthorizationStrategy()
strategy.setAllowAnonymousRead(false)
jenkins.setAuthorizationStrategy(strategy)

// mark install state as done so the setup wizard never appears
def stateFile = new File(jenkins.getRootDir(), "jenkins.install.InstallUtil.lastExecVersion")
stateFile.text = "${jenkins.VERSION}"

jenkins.save()
println "✔ init.groovy: admin user 'sentio' created, setup wizard disabled"
