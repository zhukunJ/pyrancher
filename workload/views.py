from django.shortcuts import render, redirect
from django.http import JsonResponse, QueryDict
from kubernetes import client, config
import os, hashlib, random
from k8sapi import k8s


# 无状态
def deployment(request):
    return render(request, 'workload/deployment.html')


def deployment_create(request):
    return render(request, 'workload/deployment_create.html')


def deployment_edit(request):
    return render(request, 'workload/deployment_edit.html')


def deployment_api(request):
    code = 0
    msg = ""
    auth_type = request.session.get("auth_type")
    token = request.session.get("token")
    k8s.load_auth_config(auth_type, token)
    apps_api = client.AppsV1Api()
    # 命名空间选择和命名空间表格使用
    if request.method == "GET":
        search_key = request.GET.get("search_key")
        namespace = request.GET.get("namespace")
        data = []
        try:
            for dp in apps_api.list_namespaced_deployment(namespace=namespace).items:
                name = dp.metadata.name
                namespace = dp.metadata.namespace
                replicas = dp.spec.replicas
                available_replicas = (0 if dp.status.available_replicas is None else dp.status.available_replicas)
                labels = dp.metadata.labels
                selector = dp.spec.selector.match_labels
                if len(dp.spec.template.spec.containers) > 1:
                    images = ""
                    n = 1
                    for c in dp.spec.template.spec.containers:
                        status = ("运行中" if dp.status.conditions[0].status == "True" else "异常")
                        image = c.image
                        images += "[%s]: %s / %s" % (n, image, status)
                        images += "<br>"
                        n += 1
                else:
                    status = (
                        "运行中" if dp.status.conditions[0].status == "True" else "异常")
                    image = dp.spec.template.spec.containers[0].image
                    images = "%s / %s" % (image, status)

                create_time = dp.metadata.creation_timestamp
                dp = {"name": name, "namespace": namespace, "replicas": replicas,
                      "available_replicas": available_replicas, "labels": labels, "selector": selector,
                      "images": images, "create_time": create_time}
                # 根据搜索值返回数据
                if search_key:
                    if search_key in name:
                        data.append(dp)
                else:
                    data.append(dp)
                code = 0
                msg = "获取数据成功"
        except Exception as e:
            code = 1
            status = getattr(e, "status")
            if status == 403:
                msg = "没有访问权限"
            else:
                msg = "获取数据失败"
        count = len(data)

        page = int(request.GET.get('page', 1))
        limit = int(request.GET.get('limit'))
        start = (page - 1) * limit
        end = page * limit
        data = data[start:end]

        res = {'code': code, 'msg': msg, 'count': count, 'data': data}
        return JsonResponse(res)

    elif request.method == "POST":
        name = request.POST.get("name", None)
        namespace = request.POST.get("namespace", None)
        image = request.POST.get("image", None)
        replicas = int(request.POST.get("replicas", None))
        # 处理标签
        labels = {}
        try:
            for l in request.POST.get("labels", None).split(","):
                k = l.split("=")[0]
                v = l.split("=")[1]
                labels[k] = v
        except Exception as e:
            res = {"code": 1, "msg": "标签格式错误！"}
            return JsonResponse(res)
        # resources = request.POST.get("resources", None)
        cpu_requests = request.POST.get("cpu_requests", None)
        mem_requests = request.POST.get("mem_requests", None)

        cpu_limits = request.POST.get("cpu_limits", None)
        mem_limits = request.POST.get("mem_limits", None)

        health_liveness = request.POST.get("health[liveness]",
                                           None)  # {'health[liveness]': ['on'], 'health[readiness]': ['on']}
        health_readiness = request.POST.get("health[readiness]", None)

        if cpu_requests:
            resources = client.V1ResourceRequirements(limits={"cpu": cpu_limits, "memory": mem_limits},
                                                      requests={"cpu": cpu_requests, "memory": mem_requests})
        else:
            resources = None

        # if resources == "1c2g":
        #     resources = client.V1ResourceRequirements(limits={"cpu": "1", "memory": "2Gi"},
        #                                               requests={"cpu": "0.9", "memory": "1.9Gi"})
        # elif resources == "2c4g":
        #     resources = client.V1ResourceRequirements(limits={"cpu": "2", "memory": "4Gi"},
        #                                               requests={"cpu": "1.9", "memory": "3.9Gi"})
        # elif resources == "4c8g":
        #     resources = client.V1ResourceRequirements(limits={"cpu": "4", "memory": "8Gi"},
        #                                               requests={"cpu": "3.9", "memory": "7.9Gi"})
        # else:
        #     resources = client.V1ResourceRequirements(limits={"cpu": "500m", "memory": "1Gi"},
        #                                               requests={"cpu": "450m", "memory": "900Mi"})
        liveness_probe = ""
        if health_liveness == "on":
            liveness_probe = client.V1Probe(http_get="/", timeout_seconds=30, initial_delay_seconds=30)
        readiness_probe = ""
        if health_readiness == "on":
            readiness_probe = client.V1Probe(http_get="/", timeout_seconds=30, initial_delay_seconds=30)

        for dp in apps_api.list_namespaced_deployment(namespace=namespace).items:
            if name == dp.metadata.name:
                res = {"code": 1, "msg": "Deployment已经存在！"}
                return JsonResponse(res)

        body = client.V1Deployment(
            api_version="apps/v1",
            kind="Deployment",
            metadata=client.V1ObjectMeta(name=name),
            spec=client.V1DeploymentSpec(
                replicas=replicas,
                selector={'matchLabels': labels},
                template=client.V1PodTemplateSpec(
                    metadata=client.V1ObjectMeta(labels=labels),
                    spec=client.V1PodSpec(
                        containers=[client.V1Container(
                            # https://github.com/kubernetes-client/python/blob/master/kubernetes/docs/V1Container.md
                            name="web",
                            image=image,
                            env=[{"name": "TEST", "value": "123"}, {"name": "DEV", "value": "456"}],
                            ports=[client.V1ContainerPort(container_port=80)],
                            # liveness_probe=liveness_probe,
                            # readiness_probe=readiness_probe,
                            resources=resources,
                        )]
                    )
                ),
            )
        )
        try:
            apps_api.create_namespaced_deployment(namespace=namespace, body=body)
            code = 0
            msg = "创建成功."
        except Exception as e:
            print(e)
            code = 1
            status = getattr(e, "status")
            if status == 403:
                msg = "没有访问权限！"
            else:
                msg = "创建失败！"
        res = {'code': code, 'msg': msg}
        return JsonResponse(res)

    elif request.method == "DELETE":
        request_data = QueryDict(request.body)
        name = request_data.get("name")
        namespace = request_data.get("namespace")
        auth_type = request.session.get("auth_type")
        token = request.session.get("token")
        k8s.load_auth_config(auth_type, token)
        apps_api = client.AppsV1Api()
        try:
            apps_api.delete_namespaced_deployment(namespace=namespace, name=name)
            code = 0
            msg = "删除成功."
        except Exception as e:
            code = 1
            status = getattr(e, "status")
            if status == 403:
                msg = "没有删除权限"
            else:
                msg = "删除失败！"
        res = {'code': code, 'msg': msg}
        return JsonResponse(res)


# 守护进程
def daemonset(request):
    return render(request, 'workload/daemonset.html')


def daemonset_api(request):
    code = 0
    msg = ""
    auth_type = request.session.get("auth_type")
    token = request.session.get("token")
    k8s.load_auth_config(auth_type, token)
    apps_api = client.AppsV1Api()
    if request.method == "GET":
        search_key = request.GET.get("search_key")
        namespace = request.GET.get("namespace")
        data = []
        try:
            for ds in apps_api.list_namespaced_daemon_set(namespace).items:
                name = ds.metadata.name
                namespace = ds.metadata.namespace
                desired_number = ds.status.desired_number_scheduled
                available_number = ds.status.number_available
                labels = ds.metadata.labels
                selector = ds.spec.selector.match_labels
                containers = {}
                for c in ds.spec.template.spec.containers:
                    containers[c.name] = c.image
                create_time = ds.metadata.creation_timestamp

                ds = {"name": name, "namespace": namespace, "labels": labels, "desired_number": desired_number,
                      "available_number": available_number,
                      "selector": selector, "containers": containers, "create_time": create_time}

                # 根据搜索值返回数据
                if search_key:
                    if search_key in name:
                        data.append(ds)
                else:
                    data.append(ds)
                code = 0
                msg = "获取数据成功"
        except Exception as e:
            code = 1
            status = getattr(e, "status")
            if status == 403:
                msg = "没有访问权限"
            else:
                msg = "获取数据失败"
        count = len(data)

        page = int(request.GET.get('page', 1))
        limit = int(request.GET.get('limit'))
        start = (page - 1) * limit
        end = page * limit
        data = data[start:end]

        res = {'code': code, 'msg': msg, 'count': count, 'data': data}
        return JsonResponse(res)

    elif request.method == "DELETE":
        request_data = QueryDict(request.body)
        name = request_data.get("name")
        namespace = request_data.get("namespace")
        try:
            apps_api.delete_namespaced_daemon_set(namespace=namespace, name=name)
            code = 0
            msg = "删除成功."
        except Exception as e:
            code = 1
            status = getattr(e, "status")
            if status == 403:
                msg = "没有删除权限"
            else:
                msg = "删除失败！"
        res = {'code': code, 'msg': msg}
        return JsonResponse(res)


def statefulset(request):
    return render(request, 'workload/statefulset.html')


def statefulset_api(request):
    code = 0
    msg = ""
    auth_type = request.session.get("auth_type")
    token = request.session.get("token")
    k8s.load_auth_config(auth_type, token)
    apps_api = client.AppsV1Api()
    if request.method == "GET":
        search_key = request.GET.get("search_key")
        namespace = request.GET.get("namespace")
        data = []
        try:
            for sts in apps_api.list_namespaced_stateful_set(namespace).items:
                name = sts.metadata.name
                namespace = sts.metadata.namespace
                labels = sts.metadata.labels
                selector = sts.spec.selector.match_labels
                replicas = sts.spec.replicas
                ready_replicas = ("0" if sts.status.ready_replicas is None else sts.status.ready_replicas)
                # current_replicas = sts.status.current_replicas
                service_name = sts.spec.service_name
                containers = {}
                for c in sts.spec.template.spec.containers:
                    containers[c.name] = c.image
                create_time = sts.metadata.creation_timestamp

                sts = {"name": name, "namespace": namespace, "labels": labels, "replicas": replicas,
                       "ready_replicas": ready_replicas, "service_name": service_name,
                       "selector": selector, "containers": containers, "create_time": create_time}

                # 根据搜索值返回数据
                if search_key:
                    if search_key in name:
                        data.append(sts)
                else:
                    data.append(sts)
                code = 0
                msg = "获取数据成功"
        except Exception as e:
            code = 1
            status = getattr(e, "status")
            if status == 403:
                msg = "没有访问权限"
            else:
                msg = "获取数据失败"
        count = len(data)

        page = int(request.GET.get('page', 1))
        limit = int(request.GET.get('limit'))
        start = (page - 1) * limit
        end = page * limit
        data = data[start:end]

        res = {'code': code, 'msg': msg, 'count': count, 'data': data}
        return JsonResponse(res)

    elif request.method == "DELETE":
        request_data = QueryDict(request.body)
        name = request_data.get("name")
        namespace = request_data.get("namespace")
        try:
            apps_api.delete_namespaced_stateful_set(namespace=namespace, name=name)
            code = 0
            msg = "删除成功."
        except Exception as e:
            code = 1
            status = getattr(e, "status")
            if status == 403:
                msg = "没有删除权限"
            else:
                msg = "删除失败！"
        res = {'code': code, 'msg': msg}
        return JsonResponse(res)


def pod(request):
    return render(request, 'workload/pod.html')


def pod_api(request):
    code = 0
    msg = ""
    auth_type = request.session.get("auth_type")
    token = request.session.get("token")
    k8s.load_auth_config(auth_type, token)
    core_api = client.CoreV1Api()
    if request.method == "GET":
        search_key = request.GET.get("search_key")
        namespace = request.GET.get("namespace")
        data = []
        try:
            for po in core_api.list_namespaced_pod(namespace).items:
                name = po.metadata.name
                namespace = po.metadata.namespace
                labels = po.metadata.labels
                pod_ip = po.status.pod_ip

                containers = []  # [{},{},{}]
                status = "None"
                # 只为None说明Pod没有创建（不能调度或者正在下载镜像）
                if po.status.container_statuses is None:
                    status = po.status.conditions[-1].reason
                else:
                    for c in po.status.container_statuses:
                        c_name = c.name
                        c_image = c.image

                        # 获取重启次数
                        restart_count = c.restart_count

                        # 获取容器状态
                        c_status = "None"
                        if c.ready is True:
                            c_status = "Running"
                        elif c.ready is False:
                            if c.state.waiting is not None:
                                c_status = c.state.waiting.reason
                            elif c.state.terminated is not None:
                                c_status = c.state.terminated.reason
                            # elif c.state.last_state.terminated is not None:
                            #     c_status = c.last_state.terminated.reason

                        c = {'c_name': c_name, 'c_image': c_image, 'restart_count': restart_count, 'c_status': c_status}
                        containers.append(c)

                create_time = po.metadata.creation_timestamp

                po = {"name": name, "namespace": namespace, "pod_ip": pod_ip,
                      "labels": labels, "containers": containers, "status": status,
                      "create_time": create_time}

                # 根据搜索值返回数据
                if search_key:
                    if search_key in name:
                        data.append(po)
                else:
                    data.append(po)
                code = 0
                msg = "获取数据成功"
        except Exception as e:
            code = 1
            status = getattr(e, "status")
            if status == 403:
                msg = "没有访问权限"
            else:
                msg = "获取数据失败"
        count = len(data)

        page = int(request.GET.get('page', 1))
        limit = int(request.GET.get('limit'))
        start = (page - 1) * limit
        end = page * limit
        data = data[start:end]

        res = {'code': code, 'msg': msg, 'count': count, 'data': data}
        return JsonResponse(res)

    elif request.method == "DELETE":
        request_data = QueryDict(request.body)
        name = request_data.get("name")
        namespace = request_data.get("namespace")
        try:
            core_api.delete_namespaced_pod(namespace=namespace, name=name)
            code = 0
            msg = "删除成功."
        except Exception as e:
            code = 1
            status = getattr(e, "status")
            if status == 403:
                msg = "没有删除权限"
            else:
                msg = "删除失败！"
        res = {'code': code, 'msg': msg}
        return JsonResponse(res)
