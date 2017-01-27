#!/usr/bin/env python

from subprocess import (
    CalledProcessError,
    check_call,
    check_output
)
import sys

import yaml

from charmhelpers.core.hookenv import (
    Hooks,
    UnregisteredHookError,
    config,
    resource_get,
    log,
    status_set,
    relation_get
)

from charmhelpers.fetch import (
    apt_install,
    apt_upgrade
)

from contrail_analyticsdb_utils import (
    fix_hostname,
    write_analyticsdb_config,
    launch_docker_image,
    units
)

PACKAGES = [ "docker.io" ]


hooks = Hooks()
config = config()

@hooks.hook("config-changed")
def config_changed():
    set_status()
    return None

def config_get(key):
    try:
        return config[key]
    except KeyError:
        return None

def set_status():
  try:
      result = check_output(["/usr/bin/docker",
                             "inspect",
                             "-f",
                             "{{.State.Running}}",
                             "contrail-analyticsdb"
                             ])
  except CalledProcessError:
      status_set("waiting", "Waiting for the container to be launched")
      return
  if result:
      status_set("active", "Unit ready")
  else:
      status_set("blocked", "Control container is not running")

def load_docker_image():
    img_path = resource_get("contrail-analyticsdb")
    check_call(["/usr/bin/docker",
                "load",
                "-i",
                img_path,
                ])

@hooks.hook()
def install():
    fix_hostname()
    apt_upgrade(fatal=True, dist=True)
    apt_install(PACKAGES, fatal=True)
    load_docker_image()
    #launch_docker_image()
                
@hooks.hook("contrail-control-relation-joined")
def control_joined():
   if len(units("contrail-control")) == config.get("control_units"):
       config["control-ready"] = True
   write_analyticsdb_config()

@hooks.hook("contrail-lb-relation-joined")
def lb_joined():
   config["lb-ready"] = True
   write_analyticsdb_config()

@hooks.hook("contrail-control-relation-departed")
def control_departed():
   config["control-ready"] = False

@hooks.hook("contrail-lb-relation-departed")
def lb_departed():
   config["lb-ready"] = False

@hooks.hook("identity-admin-relation-changed")
def identity_admin_changed():
   if not relation_get("service_hostname"):
        log("Keystone relation not ready")
        return
   config["identity-admin-ready"] = True
   write_analyticsdb_config()

@hooks.hook("identity-admin-relation-departed")
@hooks.hook("identity-admin-relation-broken")
def identity_admin_broken():
   config["identity-admin-ready"] = False

@hooks.hook("update-status")
def update_status():
  set_status()
  #status_set("active", "Unit ready")

def main():
    try:
        hooks.execute(sys.argv)
    except UnregisteredHookError as e:
        log("Unknown hook {} - skipping.".format(e))

if __name__ == "__main__":
    main()