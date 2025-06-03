import requests

def handle_response(response, function, *args):
    if response.status_code == 200:
        try:
            return function(response, *args)
        except ValueError:
            print("Error: Failed to parse JSON response.")
            return None
    print(f"Error: Received status code {response.status_code}")
    print(response.text)
    return None

class BitBucket:
    def __init__(self, base_url, project_key, repo_slug, auth, headers):
        self.base_url = base_url
        self.project_key = project_key
        self.repo_slug = repo_slug
        self.auth = auth
        self.headers = headers

        self.FILE_CONTENT_URL  = base_url + "/api/latest/projects/{projectKey}/repos/{repositorySlug}/browse/{path}"
        self.GET_PR_URL = base_url + "/api/latest/projects/{projectKey}/repos/{repositorySlug}/pull-requests/{pullRequestId}"
        self.DIFF_URL  = base_url + "/api/latest/projects/{projectKey}/repos/{repositorySlug}/compare/diff"
        self.DIFF_URL_RAW  = base_url + "/api/latest/projects/{projectKey}/repos/{repositorySlug}/diff"

    def get_file_path_from_object(self, json_object):
        if json_object["parent"] == "":
            return json_object["name"]
        return json_object["parent"] + "/" + json_object["name"]


    def get_changed_files_from_commits(self, from_commit: str, to_commit: str) -> dict:
            
            def discover_files(response):
                json = response.json()
                changes = {
                    "added" : [],
                    "deleted" : [],
                    "modified" : []
                }

                for diff in json["diffs"]:
                    if diff["source"] is None:
                        changes["added"].append(self.get_file_path_from_object(diff["destination"]))
                    elif diff["destination"] is None:
                        changes["deleted"].append(self.get_file_path_from_object(diff["source"]))
                    else:
                        changes["modified"].append(self.get_file_path_from_object(diff["source"]))
                
                return changes

            final_url = self.DIFF_URL.format(projectKey = self.project_key, repositorySlug = self.repo_slug)
            params = {
                "to": to_commit,
                "from": from_commit
            }
            response = requests.get(final_url, auth = self.auth, headers = self.headers, params=params)
            return handle_response(response, discover_files)

    def get_changed_files_from_commits_raw(self, from_commit: str, to_commit: str):
            final_url = self.DIFF_URL.format(projectKey = self.project_key, repositorySlug = self.repo_slug)
            params = {
                "to": to_commit,
                "from": from_commit
            }
            response = requests.get(final_url, auth = self.auth, headers = self.headers, params=params)
            return handle_response(response, lambda x: x.text)

    def get_pr_bitbucket(self, pr_id: str):
        final_url = self.GET_PR_URL.format(projectKey = self.project_key, repositorySlug = self.repo_slug, pullRequestId = pr_id)
        response = requests.get(final_url, auth = self.auth, headers = self.headers)
        return handle_response(response, lambda response: response.json())

    def get_file_content_from_bitbucket(self, file_path: str, commit: str = "") -> str:
        
        def handle_file_response(response):
            formatted_response = response.json()
            return "\n".join(line["text"] for line in formatted_response["lines"])
        
        final_url = self.FILE_CONTENT_URL.format(projectKey = self.project_key, repositorySlug = self.repo_slug, path = file_path)
        params = {
            "at" : commit,
            "limit": 10000
        }
        response = requests.get(final_url, auth = self.auth, headers = self.headers, params=params)
        return handle_response(response, handle_file_response)
