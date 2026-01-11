"""Initial schema

Revision ID: 001
Revises:
Create Date: 2024-01-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # Colors table (before articles since articles references it)
    op.create_table(
        'colors',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('name', sa.String(50), nullable=False),
        sa.Column('hex_value', sa.String(7), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # Categories table
    op.create_table(
        'categories',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('parent_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('categories.id'), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # Tags table
    op.create_table(
        'tags',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('color', sa.String(7), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # Articles table
    op.create_table(
        'articles',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('source_type', sa.String(20), nullable=False),
        sa.Column('original_url', sa.String(2048), nullable=True),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('authors', postgresql.JSONB(), nullable=True, server_default='[]'),
        sa.Column('publication_date', sa.DateTime(), nullable=True),
        sa.Column('extracted_text', sa.Text(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('summary_model', sa.String(100), nullable=True),
        sa.Column('color_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('colors.id'), nullable=True),
        sa.Column('file_path', sa.String(500), nullable=True),
        sa.Column('metadata', postgresql.JSONB(), nullable=True, server_default='{}'),
        sa.Column('processing_status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('processing_error', sa.Text(), nullable=True),
        sa.Column('search_vector', postgresql.TSVECTOR(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # Create GIN index for full-text search
    op.create_index(
        'ix_articles_search_vector',
        'articles',
        ['search_vector'],
        postgresql_using='gin'
    )

    # Article-Categories junction table
    op.create_table(
        'article_categories',
        sa.Column('article_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('articles.id'), primary_key=True),
        sa.Column('category_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('categories.id'), primary_key=True),
        sa.Column('is_primary', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('suggested_by_ai', sa.Boolean(), nullable=False, server_default='false'),
    )

    # Article-Tags junction table
    op.create_table(
        'article_tags',
        sa.Column('article_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('articles.id'), primary_key=True),
        sa.Column('tag_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tags.id'), primary_key=True),
        sa.Column('suggested_by_ai', sa.Boolean(), nullable=False, server_default='false'),
    )

    # Notes table
    op.create_table(
        'notes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('article_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('articles.id'), nullable=False, index=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # AI Providers table
    op.create_table(
        'ai_providers',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('provider_name', sa.String(50), nullable=False),
        sa.Column('display_name', sa.String(100), nullable=False),
        sa.Column('model_id', sa.String(100), nullable=False),
        sa.Column('api_key_encrypted', sa.LargeBinary(), nullable=False),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # Reorganization Suggestions table
    op.create_table(
        'reorganization_suggestions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('suggestion_type', sa.String(20), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('affected_articles', postgresql.JSONB(), nullable=True, server_default='[]'),
        sa.Column('suggested_action', postgresql.JSONB(), nullable=True, server_default='{}'),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
    )

    # Create function and trigger for updating search_vector
    op.execute("""
        CREATE OR REPLACE FUNCTION articles_search_vector_update() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector :=
                setweight(to_tsvector('english', COALESCE(NEW.title, '')), 'A') ||
                setweight(to_tsvector('english', COALESCE(NEW.summary, '')), 'B') ||
                setweight(to_tsvector('english', COALESCE(NEW.extracted_text, '')), 'C');
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER articles_search_vector_trigger
        BEFORE INSERT OR UPDATE ON articles
        FOR EACH ROW EXECUTE FUNCTION articles_search_vector_update();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS articles_search_vector_trigger ON articles")
    op.execute("DROP FUNCTION IF EXISTS articles_search_vector_update()")

    op.drop_table('reorganization_suggestions')
    op.drop_table('ai_providers')
    op.drop_table('notes')
    op.drop_table('article_tags')
    op.drop_table('article_categories')
    op.drop_index('ix_articles_search_vector', 'articles')
    op.drop_table('articles')
    op.drop_table('tags')
    op.drop_table('categories')
    op.drop_table('colors')
    op.drop_table('users')
