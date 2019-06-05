#!/usr/bin/env python

from flask import Flask, request, jsonify
from pprint import pprint
import base64
import copy
import jsonpatch
import os

app = Flask(__name__)

FROM_PREFIX = "IMAGE_FROM_"
TO_PREFIX   = "IMAGE_TO_"

@app.route('/', methods=['POST'])
def webhook():

    allowed = True
    request_info = request.json
    modified_spec = copy.deepcopy(request_info)
    uid = modified_spec["request"]["uid"]
    workload_metadata = modified_spec["request"]["object"]["metadata"]
    workload_type = modified_spec["request"]["kind"]["kind"]
    namespace = modified_spec["request"]["namespace"]

    print("")
    print("##################################################################")
    print("")

    # Detect if "name" in object metadata
    # this was added because the request object for pods don't 
    # include a "name" field in the object metadata. This is because generateName
    # occurs Server Side post-admission
    if "name" in workload_metadata:
        
        workload = modified_spec["request"]["object"]["metadata"]["name"]

    elif "generateName" in workload_metadata:

        workload = modified_spec["request"]["object"]["metadata"]["generateName"]

    else:

        workload = uid

    #pprint(request_info)

    # Change workflow/json path based on K8s object type
    if workload_type == "Pod":

        for container_spec in modified_spec["request"]["object"]["spec"]["containers"]:
        
            print("[INFO] - Processing container: {}/{}".format(namespace,workload))
            swap_image(container_spec)

    else:

        for container_spec in modified_spec["request"]["object"]["spec"]["template"]["spec"]["containers"]:

            print("[INFO] - Processing container: {}/{}".format(namespace,workload))
            swap_image(container_spec)

    print("[INFO] - Diffing original request to modified request and generating JSONPatch")


    #print("Original Spec:")
    #pprint(request_info["request"]["object"]["spec"]["containers"])
    #print("Modified Spec:")
    #pprint(modified_spec["request"]["object"]["spec"]["containers"])

    patch = jsonpatch.JsonPatch.from_diff(request_info["request"]["object"], modified_spec["request"]["object"])

    print("[INFO] - JSON Patch: {}".format(patch))

    admission_response = {
        "allowed": True,
        "uid": request_info["request"]["uid"],
        "patch": base64.b64encode(str(patch).encode()).decode(),
        "patchtype": "JSONPatch"
    }
    admissionReview = {
        "response": admission_response
    }

    print("[INFO] - Sending Response to K8s API Server:")
    pprint(admissionReview)
    return jsonify(admissionReview)


def swap_image(container_spec):

    name = container_spec["name"]
    image = container_spec["image"]
    new_image = image
    swap = swap_images()

    print("[INFO] - Swapping image definition for container spec: {}".format(name))

    for fromStr, toStr in swap:
        new_image = image.replace(fromStr, toStr, 1)
        if new_image != image:
            break

    if new_image != image:
        print ("[INFO] - image does not match requested swap images, nothing to do")

    else:

        print ("[INFO] - Substitution image definition detected: {}".format(image))
        print ("[INFO] - Image updated to : {}".format(new_image))

        container_spec["image"] = new_image
        container_spec["imagePullPolicy"] = "Always"

def swap_images():
    imgs = []
    for k, v in os.environ:
        if k.startswith(FROM_PREFIX):
            toKey = TO_PREFIX + k[len(FROM_PREFIX):]
            if toKey in os.environ:
                imgs.append((v, os.environ[toKey]))
    return imgs

def swap_image(img, swap):

app.run(host='0.0.0.0', port=5000, debug=True, ssl_context=('./ssl/cert.pem', './ssl/key.pem'))

