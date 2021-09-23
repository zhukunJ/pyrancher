import os
from kubernetes import client, config

# HTTPS证书认证（kubeconfig）：
config.load_kube_config("/Users/admin/.kube/config.rks")  # 指定kubeconfig配置文件
apps_api = client.AppsV1Api()  # 资源接口类实例化
for dp in apps_api.list_namespaced_deployment("nginx").items:
    print(dp)  # 取nginx空间下所有的deploy数据
    print(dp.metadata.labels)  # 取所有标签
    print(dp.metadata.labels['app'])  # 取标签app的值
    print(dp.metadata.name)  # 取deploy名称
    for i in dp.metadata.labels:  # 自定义格式取所有标签
        print("标签名称", i, "标签值：", dp.metadata.labels[i])
# ---------------------------------------------------------------------

# HTTP Token认证（ServiceAccount）：
# configuration = client.Configuration()
# configuration.host = "https://106.14.154.228:6443"  # APISERVER地址
# # configuration.ssl_ca_cert="ca.crt"  # CA证书 （ca证书也可以不用指定，但是需要开启configuration.verify_ssl = False ）
# configuration.verify_ssl = False  # 启用证书验证（ca证书也可以不用指定，但是需要开启configuration.verify_ssl = False ）
# token = ''
# with open('token', 'r') as f:  # 容器中token位置指定在地址在/var/run/secrets/kubernetes.io/serviceaccount
#     for line in f.readlines():
#         line = line.strip()
#         token += line
# configuration.api_key = {"authorization": "Bearer " + token}  # 指定Token字符串
# client.Configuration.set_default(configuration)
# apps_api = client.AppsV1Api()
# for dp in apps_api.list_namespaced_deployment("nginx").items:
# print(dp)  # 取nginx空间下所有的deploy数据
#     print(dp.metadata.labels)  # 取所有标签
#     print(dp.metadata.labels['app'])  # 取标签app的值
#     print(dp.metadata.name)  # 取deploy名称
#     for i in dp.metadata.labels:  # 自定义格式取所有标签
#         print("标签名称", i, "标签值：", dp.metadata.labels[i])
# ---------------------------------------------------------------------

# 操作演练示例
# configuration = client.Configuration()
# configuration.host = "https://106.14.154.228:6443"  # APISERVER地址
# configuration.ssl_ca_cert="ca.crt"  # CA证书 （ca证书也可以不用指定，但是需要开启configuration.verify_ssl = False ）
# configuration.verify_ssl = False  # 启用证书验证（ca证书也可以不用指定，但是需要开启configuration.verify_ssl = False ）
# token = ''
# with open('token', 'r') as f:  # 容器中token位置指定在地址在/var/run/secrets/kubernetes.io/serviceaccount
#     for line in f.readlines():
#         line = line.strip()
#         token += line
# configuration.api_key = {"authorization": "Bearer " + token}  # 指定Token字符串
# client.Configuration.set_default(configuration)
# apps_api = client.AppsV1Api()
# core_api = client.CoreV1Api()
# deployment操作
# ------------------查询
# for dp in apps_api.list_namespaced_deployment("nginx").items:
# print(dp)  # 取nginx空间下所有的deploy数据
#     print(dp.metadata.labels)  # 取所有标签
#     print(dp.metadata.labels['app'])  # 取标签app的值
#     print(dp.metadata.name)  # 取deploy名称
#     for i in dp.metadata.labels:  # 自定义格式取所有标签
#         print("标签名称", i, "标签值：", dp.metadata.labels[i])

# ------------------创建
# namespace = "nginx"
# name = "api-test"
# replicas = 1
# labels = {'a': '1', 'b': '2'}  # 不区分数据类型，都要加引号
# image = "nginx"
# body = client.V1Deployment(
#     api_version="apps/v1",
#     kind="Deployment",
#     metadata=client.V1ObjectMeta(name=name),
#     spec=client.V1DeploymentSpec(
#         replicas=replicas,
#         selector={'matchLabels': labels},
#         template=client.V1PodTemplateSpec(
#             metadata=client.V1ObjectMeta(labels=labels),
#             spec=client.V1PodSpec(
#                 containers=[client.V1Container(
#                     name="web",
#                     image=image
#                 )]
#             )
#         ),
#     )
# )
# try:
#     apps_api.create_namespaced_deployment(namespace=namespace, body=body)
# except Exception as e:
#     status = getattr(e, "status")
#     if status == 400:
#         print(e)
#         print("格式错误")
#     elif status == 403:
#         print("没权限")

# ------------------删除
# namespace = "nginx"
# name = "api-test"
# apps_api.delete_namespaced_deployment(namespace=namespace, name=name)


# Service操作
# ------------------查询
# for svc in core_api.list_namespaced_service(namespace="nginx").items:
#     print(svc.metadata.name)

# ------------------创建
# namespace = "nginx"
# name = "api-test"
# selector = {'a': '1', 'b': '2'}  # 不区分数据类型，都要加引号
# port = 80
# target_port = 80
# type = "NodePort"
# body = client.V1Service(
#     api_version="v1",
#     kind="Service",
#     metadata=client.V1ObjectMeta(
#         name=name
#     ),
#     spec=client.V1ServiceSpec(
#         selector=selector,
#         ports=[client.V1ServicePort(
#             port=port,
#             target_port=target_port
#         )],
#         type=type
#     )
# )
# core_api.create_namespace`d_service(namespace=namespace, body=body)

# ------------------删除
# core_api.delete_namespaced_service(namespace=namespace, name=name)
