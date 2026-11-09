# upstream

`gephi-plugins/GephiAI-pom.xml` is the pom that gephi/gephi-plugins builds this plugin from
(`modules/GephiAI/pom.xml` on branch `master-forge`, parent `org.gephi:gephi-plugin-parent`).
The `.nbm` that Gephi's plugin list offers is built from that file, not from
`gephi-ai-plugin/pom.xml`. It is the upstream pom with one change: `maven-surefire-plugin` is
pinned to 3.6.0, the version `gephi-ai-plugin/pom.xml` uses, because Gephi's CI warned that the
version was missing.

The `gephi-plugins` CI job in `.github/workflows/ci.yml` builds this plugin the way Gephi does:
it checks out gephi/gephi-plugins, drops in `gephi-ai-plugin/src` and this pom, and runs Maven.

The next gephi-plugins pull request should carry this pom as `modules/GephiAI/pom.xml`.
