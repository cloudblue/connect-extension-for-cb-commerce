# CloudBlue Connect Extension

## Background
In this folder is stored the APS package for CloudBlue to use together with the HUB APP,
HUB APP is in charge to operate in centralized manner following things:

* Tier Configurations for Providers and Resellers
* Tier Account Changes
* Product operations, such as installation, upgrade..
* Health Checks of CB Commerce against Connect
* Etc

## Building Sources

On build time of the image, sources will not be rebuild, reason is to not make build process fat,
this is due building the package requires apstools and due it java, something we don't want on
extension-cbc images, due it you must manually build the image following this instructions in case of
changes.


### Building with apstools

Build can be initiated by following command:

```
apsbuild src -o CloudBlue-Connect-Extension.app.zip
```

### Important remark

Do not remove sources on build time, APP-META is used to inform CB Commerce about new versions
available
