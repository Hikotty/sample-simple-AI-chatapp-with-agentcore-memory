# フロントエンド（生 HTML/CSS/JS）は S3 + CloudFront から配信し、/api/* だけ EC2 へ転送する。
# CloudFront のデフォルト証明書で https になる。

locals {
  static_dir = "${path.module}/../app/static"
  static_files = {
    "index.html" = { key = "index.html", type = "text/html; charset=utf-8" }
    "style.css"  = { key = "static/style.css", type = "text/css; charset=utf-8" }
    "app.js"     = { key = "static/app.js", type = "application/javascript; charset=utf-8" }
  }
}

resource "aws_s3_bucket" "static" {
  bucket        = "${local.name}-static-${data.aws_caller_identity.current.account_id}"
  force_destroy = true
  tags          = { Name = "${local.name}-static" }
}

resource "aws_s3_bucket_public_access_block" "static" {
  bucket                  = aws_s3_bucket.static.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_object" "static" {
  for_each     = local.static_files
  bucket       = aws_s3_bucket.static.id
  key          = each.value.key
  source       = "${local.static_dir}/${each.key}"
  content_type = each.value.type
  etag         = filemd5("${local.static_dir}/${each.key}")
}

resource "aws_cloudfront_origin_access_control" "static" {
  name                              = "${local.name}-static-oac"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# OAC 経由の CloudFront だけに S3 の読み取りを許可
data "aws_iam_policy_document" "static_bucket" {
  statement {
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.static.arn}/*"]
    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.app.arn]
    }
  }
}

resource "aws_s3_bucket_policy" "static" {
  bucket = aws_s3_bucket.static.id
  policy = data.aws_iam_policy_document.static_bucket.json
}

# CloudFront のマネージドポリシー
data "aws_cloudfront_cache_policy" "caching_optimized" {
  name = "Managed-CachingOptimized"
}
data "aws_cloudfront_cache_policy" "caching_disabled" {
  name = "Managed-CachingDisabled"
}
data "aws_cloudfront_origin_request_policy" "all_viewer" {
  name = "Managed-AllViewer"
}

resource "aws_cloudfront_distribution" "app" {
  enabled             = true
  comment             = "${local.name}: static from S3, /api/* to EC2"
  default_root_object = "index.html"
  price_class         = "PriceClass_100"

  origin {
    origin_id                = "s3-static"
    domain_name              = aws_s3_bucket.static.bucket_regional_domain_name
    origin_access_control_id = aws_cloudfront_origin_access_control.static.id
  }

  origin {
    origin_id   = "ec2-api"
    domain_name = aws_eip.app.public_dns
    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "http-only"
      origin_ssl_protocols   = ["TLSv1.2"]
      origin_read_timeout    = 60 # SSE のトークン間隔を待てるように
    }
  }

  default_cache_behavior {
    target_origin_id       = "s3-static"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    cache_policy_id        = data.aws_cloudfront_cache_policy.caching_optimized.id
    compress               = true
  }

  ordered_cache_behavior {
    path_pattern             = "/api/*"
    target_origin_id         = "ec2-api"
    viewer_protocol_policy   = "https-only"
    allowed_methods          = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
    cached_methods           = ["GET", "HEAD"]
    cache_policy_id          = data.aws_cloudfront_cache_policy.caching_disabled.id
    origin_request_policy_id = data.aws_cloudfront_origin_request_policy.all_viewer.id
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  tags = { Name = local.name }
}

output "cloudfront_url" {
  value = "https://${aws_cloudfront_distribution.app.domain_name}/"
}
