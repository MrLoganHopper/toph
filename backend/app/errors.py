class AppError(Exception):
    def __init__(self,status,code,message,retryable=False,retry_after=None,recording_id=None):
        super().__init__(message)
        self.status,self.code,self.message=status,code,message
        self.retryable,self.retry_after,self.recording_id=retryable,retry_after,recording_id

def not_found():
    raise AppError(404,'NOT_FOUND','This resource is unavailable.')

def missing_config(**values):
    absent=[key for key,value in values.items() if not value]
    if absent:
        raise AppError(503,'CONFIGURATION_REQUIRED','An administrator must configure: '+', '.join(absent)+'.',True)
